"""
LLM Code Deployment System - Main Application
==============================================

A FastAPI-based automated deployment system that:
- Receives app briefs via REST API
- Generates complete web applications using LLM (via AIpipe OpenRouter)
- Creates GitHub repositories and deploys to GitHub Pages
- Handles iterative revisions (Round 1 & Round 2)
- Notifies evaluation APIs with deployment results
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os
import json
import base64
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import re
import time

# Initialize FastAPI application
app = FastAPI(title="LLM Code Deployment System")

# ============================================================================
# CONFIGURATION - Environment Variables
# ============================================================================
AIPIPE_API_URL = os.getenv("AIPIPE_API_URL", "") # AIpipe OpenRouter endpoint
AIPIPE_API_KEY = os.getenv("AIPIPE_API_KEY", "") # AIpipe API key
AIPIPE_MODEL = os.getenv("AIPIPE_MODEL", "openai/gpt-4.1") # Model selection
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "") # GitHub Personal Access Token
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL", "") # Student email for verification
STUDENT_SECRET = os.getenv("STUDENT_SECRET", "") # Secret for request validation

# GitHub API base URL
GITHUB_API = "https://api.github.com"

# ============================================================================
# LLM CLIENT - AIpipe OpenRouter Integration
# ============================================================================
class LLMClient:
    """
    LLM client for generating code via AIpipe OpenRouter.
    
    Supports two models:
    - openai/gpt-4.1 (faster, good quality)
    - anthropic/claude-sonnet-4.5 (slower, excellent quality)
    
    Includes automatic fallback from Claude to GPT-4.1 if primary model fails.
    """    
    def __init__(self, api_url: str, api_key: str, model: str = "openai/gpt-4.1"):
        """
        Initialize LLM client with API credentials and model selection.
        
        Args:
            api_url: AIpipe OpenRouter API endpoint
            api_key: API authentication key
            model: Model identifier (defaults to openai/gpt-4.1)
        """
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

        # Validate model against supported options
        supported_models = [
            "openai/gpt-4.1",
            "anthropic/claude-sonnet-4.5"
        ]
        if self.model not in supported_models:
            print(f"Warning: Model {self.model} not in supported list. Using openai/gpt-4.1")
            self.model = "openai/gpt-4.1"
    
    async def generate(self, prompt: str, max_tokens: int = 5000) -> str:
        """
        Generate code using LLM via AIpipe OpenRouter.
        
        Implements automatic fallback logic:
        - If Claude Sonnet 4.5 fails, retries with GPT-4.1
        - If GPT-4.1 fails, raises exception
        
        Args:
            prompt: Detailed prompt describing the application to generate
            max_tokens: Maximum tokens in response (default: 5000)
            
        Returns:
            str: Generated code/content from LLM
            
        Raises:
            Exception: If LLM generation fails for all models
        """                 
        try:
            return await self._openrouter_format(prompt, max_tokens)
        except Exception as e:
            # Implement fallback logic for Claude -> GPT-4.1
            if self.model == "anthropic/claude-sonnet-4.5":
                print("Primary model failed. Retrying with fallback model openai/gpt-4.1")
                self.model = "openai/gpt-4.1"
                try:
                    return await self._openrouter_format(prompt, max_tokens)
                except Exception as fallback_error:
                    print(f"AIpipe OpenRouter API failed: {fallback_error}")
                    raise Exception(f"LLM generation failed: {str(fallback_error)}")
            else:
                print(f"AIpipe OpenRouter API failed: {e}")
                raise Exception(f"LLM generation failed: {str(e)}")
    
    async def _openrouter_format(self, prompt: str, max_tokens: int) -> str:
        """
        Make API request to AIpipe OpenRouter in OpenAI-compatible format.
        
        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum response length
            
        Returns:
            str: Model's response content
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.5 # Balance between creativity and consistency
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

# ============================================================================
# GITHUB MANAGER - Repository Operations
# ============================================================================
class GitHubManager:
    """
    Manages all GitHub repository operations using GitHub REST API.
    
    Handles:
    - Repository creation
    - File uploads and updates
    - GitHub Pages activation
    - Pages deployment verification
    """    
    def __init__(self, token: str):
        """
        Initialize GitHub manager with authentication token.
        
        Args:
            token: GitHub Personal Access Token (fine-grained)
        """
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json" # GitHub API v3
        }
    
    async def repo_exists(self, owner: str, repo: str) -> bool:
        """
        Check if a repository already exists.
        
        Used to determine if Round 2 update is valid or if repo needs creation.
        
        Args:
            owner: GitHub username
            repo: Repository name
            
        Returns:
            bool: True if repository exists, False otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}",
                    headers=self.headers
                )
                return response.status_code == 200
            except:
                return False
    
    async def create_repo(self, repo_name: str, description: str) -> Dict:
        """
        Create a new public GitHub repository.
        
        Args:
            repo_name: Unique name for the repository
            description: Repository description
            
        Returns:
            dict: GitHub API response with repository details
            
        Raises:
            httpx.HTTPStatusError: If repository creation fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API}/user/repos",
                headers=self.headers,
                json={
                    "name": repo_name,
                    "description": description,
                    "private": False,
                    "auto_init": False
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_file_sha(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        Get the SHA hash of a file if it exists in the repository.
        
        Required for updating existing files via GitHub API.
        
        Args:
            owner: GitHub username
            repo: Repository name
            path: File path in repository
            
        Returns:
            str: SHA hash if file exists, None otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get('sha')
            except:
                pass
        return None
    
    async def create_or_update_file(self, owner: str, repo: str, path: str, 
                                   content: str, message: str, sha: Optional[str] = None):
        """
        Create a new file or update an existing file in repository.
        
        Args:
            owner: GitHub username
            repo: Repository name
            path: File path in repository
            content: File content as string
            message: Commit message
            sha: SHA hash of existing file (required for updates)
            
        Returns:
            dict: GitHub API response with commit details
            
        Raises:
            httpx.HTTPStatusError: If file operation fails
        """
        async with httpx.AsyncClient() as client:
            # GitHub API requires base64-encoded content
            data = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode()
            }
            if sha:
                data["sha"] = sha # Required for updates
            
            response = await client.put(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    async def enable_pages(self, owner: str, repo: str):
        """
        Enable GitHub Pages for the repository.
        
        Configures Pages to deploy from main branch root directory.
        
        Args:
            owner: GitHub username
            repo: Repository name
            
        Raises:
            httpx.HTTPStatusError: If Pages activation fails (except 409 conflict)
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/pages",
                    headers=self.headers,
                    json={
                        "source": {
                            "branch": "main",
                            "path": "/" # Deploy from root directory
                        }
                    }
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 409:
                    # 409 Conflict means Pages is already enabled
                    print("Pages already enabled")
                else:
                    raise
    
    async def verify_pages_live(self, pages_url: str, max_attempts: int = 20) -> bool:
        """
        Verify that GitHub Pages deployment is live and accessible.
        
        Polls the Pages URL until it returns HTTP 200 or max attempts reached.
        Each attempt waits 10 seconds, allowing ~3 minutes total for deployment.
        
        Args:
            pages_url: Full GitHub Pages URL (e.g., https://user.github.io/repo/)
            max_attempts: Maximum number of verification attempts (default: 20)
            
        Returns:
            bool: True if Pages is live and accessible, False otherwise
        """
        print(f"Verifying GitHub Pages is live: {pages_url}")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.get(pages_url, timeout=10.0)
                    if response.status_code == 200:
                        print(f"[OK] GitHub Pages is live! (attempt {attempt + 1})")
                        return True
                    else:
                        print(f"Attempt {attempt + 1}: Status {response.status_code}")
                except Exception as e:
                    print(f"Attempt {attempt + 1}: {str(e)[:50]}")

                # Wait 10 seconds between attempts
                if attempt < max_attempts - 1:
                    await asyncio.sleep(10)

        # Deployment verification timed out, but continue anyway
        print("[WARNING] Could not verify Pages is live, but continuing...")
        return False
    
    async def get_user(self) -> Dict:
        """
        Get authenticated user information from GitHub.
        
        Used to determine the repository owner username.
        
        Returns:
            dict: User information including login (username)
            
        Raises:
            httpx.HTTPStatusError: If authentication fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API}/user",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# ============================================================================
# ATTACHMENT PROCESSOR - Handle Data URIs
# ============================================================================
class AttachmentProcessor:
    """
    Processes file attachments encoded as data URIs.
    
    Handles decoding and content extraction for:
    - Text files (CSV, JSON, Markdown, plain text)
    - Binary files (images, PDFs)
    """    
    @staticmethod
    def decode_data_uri(data_uri: str) -> tuple[str, bytes]:
        """
        Decode a data URI into MIME type and content bytes.
        
        Data URI format: data:<mime_type>;base64,<base64_encoded_content>
        
        Args:
            data_uri: Data URI string
            
        Returns:
            tuple: (mime_type, content_bytes)
        """
        try:
            # Parse data URI using regex
            match = re.match(r'data:([^;]+);base64,(.+)', data_uri)
            if match:
                mime_type = match.group(1)
                base64_content = match.group(2)
                content = base64.b64decode(base64_content)
                return mime_type, content
        except Exception as e:
            print(f"Error decoding data URI: {e}")
        return "application/octet-stream", b""
    
    @staticmethod
    def process_attachments(attachments: List[Dict]) -> List[Dict]:
        """
        Process list of attachments and extract usable content.
        
        For text files (CSV, JSON, MD), attempts to decode as UTF-8 text.
        For binary files, preserves raw bytes.
        
        Args:
            attachments: List of attachment dicts with 'name' and 'url' keys
            
        Returns:
            list: Processed attachments with additional metadata:
                - mime_type: File MIME type
                - data_uri: Original data URI
                - content: Raw bytes
                - text_content: Decoded text (for text files only)
                - size: Content size in bytes
        """
        processed = []
        for att in attachments:
            name = att.get('name', 'unknown')
            url = att.get('url', '')
            
            if url.startswith('data:'):
                mime_type, content = AttachmentProcessor.decode_data_uri(url)

                # Try to decode text content for common text MIME types
                text_content = None
                if mime_type in ['text/csv', 'application/json', 'text/markdown', 'text/plain']:
                    try:
                        text_content = content.decode('utf-8')
                    except:
                        pass
                
                processed.append({
                    'name': name,
                    'mime_type': mime_type,
                    'data_uri': url,
                    'content': content,
                    'text_content': text_content, # Will be None for binary files
                    'size': len(content)
                })
            else:
                # Non-data URI attachments (e.g., external URLs)
                processed.append({
                    'name': name,
                    'url': url
                })
        
        return processed

# ============================================================================
# CODE GENERATOR - LLM-Powered Application Generation
# ============================================================================
class CodeGenerator:
    """
    Generates complete web applications using LLM based on task briefs.
    
    Responsibilities:
    - Construct detailed prompts for LLM
    - Parse LLM responses to extract files (HTML, README)
    - Generate MIT license text
    """    
    def __init__(self, llm_client: LLMClient):
        """
        Initialize code generator with LLM client.
        
        Args:
            llm_client: Configured LLMClient instance
        """
        self.llm = llm_client
    
    async def generate_app(self, brief: str, checks: List[str], 
                          attachments: List[Dict], task_id: str) -> Dict[str, str]:
        """
        Generate complete application code based on task brief.
        
        Args:
            brief: Task description and requirements
            checks: List of evaluation checks the app must satisfy
            attachments: File attachments (data URIs)
            task_id: Unique task identifier
            
        Returns:
            dict: Generated files with keys 'index.html' and 'README.md'
        """
        # Process attachments to extract usable content
        processed_attachments = AttachmentProcessor.process_attachments(attachments)

        # Build comprehensive prompt for LLM
        prompt = self._build_prompt(brief, checks, processed_attachments, task_id)

        # Get LLM response
        response = await self.llm.generate(prompt)

        # Parse the response to extract files
        files = self._parse_response(response)
        
        return files
    
    def _build_prompt(self, brief: str, checks: List[str], 
                     attachments: List[Dict], task_id: str) -> str:
        """
        Build detailed prompt for LLM to generate application code.
        
        Includes:
        - Task brief and requirements
        - Attachment contents (for text files) or metadata (for binary)
        - Evaluation checks
        - Specific formatting instructions
        
        Args:
            brief: Task description
            checks: Evaluation checks
            attachments: Processed attachments with content
            task_id: Task identifier
            
        Returns:
            str: Complete prompt for LLM
        """
        # Format attachments information
        attachments_info = ""
        if attachments:
            attachments_info = "\n\nATTACHMENTS PROVIDED:\n"
            for att in attachments:
                if att.get('text_content'):
                    # For text files, include actual content
                    attachments_info += f"\n--- {att['name']} ({att['mime_type']}) ---\n"
                    attachments_info += att['text_content'][:1000]  # First 1000 chars
                    if len(att['text_content']) > 1000:
                        attachments_info += "\n... (truncated)"
                    attachments_info += "\n"
                else:
                    # For binary files, just mention them
                    attachments_info += f"- {att['name']}: {att.get('mime_type', 'unknown type')}\n"
                    attachments_info += f"  Data URI: {att.get('data_uri', 'N/A')[:100]}...\n"

        # Format evaluation checks
        checks_info = "\n\nEVALUATION CHECKS:\n" + "\n".join(f"- {check}" for check in checks)

        # Construct complete prompt
        prompt = f"""You are an expert web developer. Create a complete, production-ready single-page web application.

TASK: {brief}

{attachments_info}

{checks_info}

REQUIREMENTS:
1. Create a COMPLETE, WORKING HTML file with embedded CSS and JavaScript
2. Use CDN links for any libraries (Bootstrap, marked, highlight.js, Chart.js, etc.)
3. Handle all attachments by embedding data URIs directly in the code OR processing the data shown above
4. If attachments contain CSV/JSON data, parse and use it in your code
5. Implement ALL functionality specified in the brief
6. Ensure all evaluation checks will pass
7. Include proper error handling
8. Write clean, well-commented code
9. Make it visually appealing with modern styling
10. Ensure the app works standalone without any server

RESPONSE FORMAT:
Provide your response in this exact format:

=== index.html ===
[Complete HTML code here - must be fully functional]

=== README.md ===
# {task_id}

## Overview
[Brief description of the application]

## Features
[List of key features]

## Setup Instructions
1. Clone the repository
2. Open index.html in a web browser
3. The application runs entirely client-side

## Usage
[How to use the application]

## Code Explanation
[Brief explanation of how the code works]

## Technologies Used
[List of libraries and technologies]

## License
MIT License

IMPORTANT:
- The index.html must be COMPLETE and SELF-CONTAINED
- Do NOT use placeholders or TODO comments
- Implement FULL functionality
- All code must work when deployed to GitHub Pages
- For CSV data, parse it directly in JavaScript
- For JSON data, embed it as a variable or parse from data URI
- Test all evaluation checks in your mind before responding

Generate the complete application now:"""
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, str]:
        """
        Parse LLM response to extract file contents.
        
        Looks for files in === filename === format or ```language code blocks.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            dict: Extracted files with keys 'index.html' and 'README.md'
        """
        files = {}

        # Extract index.html using === delimiter
        html_match = re.search(r'===\s*index\.html\s*===\s*(.*?)(?====|$)', 
                              response, re.DOTALL | re.IGNORECASE)
        if html_match:
            files['index.html'] = html_match.group(1).strip()

        # Extract README.md using === delimiter
        readme_match = re.search(r'===\s*README\.md\s*===\s*(.*?)(?====|$)', 
                                response, re.DOTALL | re.IGNORECASE)
        if readme_match:
            files['README.md'] = readme_match.group(1).strip()

        # Fallback: Try to extract from code blocks if delimiter parsing failed
        if not files.get('index.html'):
            html_blocks = re.findall(r'```html\s*(.*?)```', response, re.DOTALL | re.IGNORECASE)
            if html_blocks:
                files['index.html'] = html_blocks[0].strip()
        
        if not files.get('README.md'):
            md_blocks = re.findall(r'```markdown\s*(.*?)```', response, re.DOTALL | re.IGNORECASE)
            if md_blocks:
                files['README.md'] = md_blocks[0].strip()

        # Clean up any remaining code block markers
        for key in files:
            files[key] = files[key].replace('```html', '').replace('```markdown', '').replace('```', '').strip()
        
        return files
    
    def get_mit_license(self) -> str:
        """
        Generate MIT License text with current year.
        
        Returns:
            str: Complete MIT License text
        """
        year = datetime.now().year
        return f"""MIT License

Copyright (c) {year}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

# ============================================================================
# DEPLOYMENT MANAGER - Orchestrates Complete Workflow
# ============================================================================
class DeploymentManager:
    """
    Orchestrates the complete deployment workflow from task receipt to notification.
    
    Workflow:
    1. Generate application code using LLM
    2. Create/update GitHub repository
    3. Upload files (HTML, README, LICENSE)
    4. Enable and verify GitHub Pages
    5. Notify evaluation API
    """    
    def __init__(self):
        """
        Initialize deployment manager with LLM, GitHub, and code generator.
        """
        self.llm = LLMClient(AIPIPE_API_URL, AIPIPE_API_KEY, AIPIPE_MODEL)
        self.github = GitHubManager(GITHUB_TOKEN)
        self.generator = CodeGenerator(self.llm)

    def _ensure_round2_marker(self, readme_content: str, round_num: int) -> str:
        """
        Ensure Round 2 marker is properly added to README content.
        
        This method:
        1. Removes any existing Round 2 markers to avoid duplicates
        2. Adds a clear, consistent Round 2 marker if round_num is 2
        
        Args:
            readme_content: Original README content
            round_num: Current round number
            
        Returns:
            str: README content with Round 2 marker added (if applicable)
        """
        if round_num != 2:
            return readme_content
        
        # Remove any existing Round 2 markers (to avoid duplicates)
        # This handles various possible formats of the marker
        patterns_to_remove = [
            r'\n---\n.*?Round 2.*?\n',
            r'\n##.*?Round 2.*?\n.*?\n',
            r'\n\*\*Note:\*\*.*?Round 2.*?\n',
            r'\n✅.*?Round 2.*?\n'
        ]
        
        cleaned_content = readme_content
        for pattern in patterns_to_remove:
            cleaned_content = re.sub(pattern, '\n', cleaned_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Add the Round 2 marker at the end
        round2_marker = "\n\n---\n\n✅ **This repository has been updated for Round 2 of the evaluation cycle.**\n\nThe application has been enhanced based on feedback from the initial evaluation.\n"
        
        return cleaned_content.rstrip() + round2_marker
    
    async def deploy(self, task_data: Dict) -> Dict:
        """
        Execute complete deployment workflow.
        
        Handles both Round 1 (new repo) and Round 2 (update existing repo).
        
        Args:
            task_data: Task request data including brief, checks, attachments
            
        Returns:
            dict: Deployment result with repo_url, commit_sha, pages_url
            
        Raises:
            Exception: If Round 2 is requested but repo doesn't exist
        """
        # Extract task information
        repo_name = f"{task_data['task']}"
        round_num = task_data.get('round', 1)

        # Get authenticated GitHub user
        user = await self.github.get_user()
        owner = user['login']

        # Check if repository already exists
        repo_exists = await self.github.repo_exists(owner, repo_name)

        # Validate Round 2 requests
        if round_num == 2 and not repo_exists:
            raise Exception(f"Round 2 request but repo {repo_name} doesn't exist!")

        # Warn if repo exists for Round 1 (will update instead of fail)
        if round_num == 1 and repo_exists:
            print(f"Warning: Repo {repo_name} already exists for Round 1. Will update it.")

        # Generate application code using LLM
        print(f"Generating code for {repo_name} (Round {round_num})...")
        files = await self.generator.generate_app(
            task_data['brief'],
            task_data['checks'],
            task_data.get('attachments', []),
            task_data['task']
        )

        # Create repository if it doesn't exist (Round 1)
        if not repo_exists:
            print(f"Creating repository {owner}/{repo_name}...")
            repo = await self.github.create_repo(
                repo_name,
                f"Auto-generated app for task: {task_data['task']} - Round {round_num}"
            )
        else:
            # Update existing repository (Round 2)
            print(f"Updating existing repository {owner}/{repo_name} (Round {round_num})...")
            if round_num == 2:
                # Update GitHub repo 'About' description to reflect Round 2
                try:
                    async with httpx.AsyncClient() as client:
                        await client.patch(
                            f"{GITHUB_API}/repos/{owner}/{repo_name}",
                            headers=self.github.headers,
                            json={"description": f"Auto-generated app for task: {task_data['task']} - Updated for Round 2"}
                        )
                except Exception as e:
                    print(f"[WARNING] Could not update repo description: {e}")
        
        # Upload/update files to repository
        print("Uploading files...")

        # Upload index.html (get SHA first if updating)
        if 'index.html' in files:
            sha = await self.github.get_file_sha(owner, repo_name, "index.html")
            await self.github.create_or_update_file(
                owner, repo_name, "index.html",
                files['index.html'],
                f"Round {round_num}: Update index.html" if sha else "Initial commit: Add index.html",
                sha
            )

        # Upload README.md (get SHA first if updating)
        if 'README.md' in files:
            sha = await self.github.get_file_sha(owner, repo_name, "README.md")
            readme_content = self._ensure_round2_marker(files['README.md'], round_num)
            await self.github.create_or_update_file(
                owner, repo_name, "README.md",
                readme_content,
                f"Round {round_num}: Update README.md" if sha else "Add README.md",
                sha
            )

        # Upload LICENSE (only if it doesn't already exist)
        license_sha = await self.github.get_file_sha(owner, repo_name, "LICENSE")
        if not license_sha:
            await self.github.create_or_update_file(
                owner, repo_name, "LICENSE",
                self.generator.get_mit_license(),
                "Add MIT LICENSE"
            )

        # Enable GitHub Pages
        print("Enabling GitHub Pages...")
        await self.github.enable_pages(owner, repo_name)

        # Verify GitHub Pages is live
        pages_url = f"https://{owner}.github.io/{repo_name}/"
        await self.github.verify_pages_live(pages_url)

        # Get latest commit SHA for reporting
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo_name}/commits/main",
                headers=self.github.headers
            )
            commit_data = response.json()
            commit_sha = commit_data['sha']

        # Prepare result for evaluation API
        result = {
            "email": task_data['email'],
            "task": task_data['task'],
            "round": task_data['round'],
            "nonce": task_data['nonce'],
            "repo_url": f"https://github.com/{owner}/{repo_name}",
            "commit_sha": commit_sha,
            "pages_url": pages_url
        }
        
        return result
    
    async def notify_evaluation(self, evaluation_url: str, result: Dict) -> bool:
        """
        Notify evaluation API with deployment results.
        
        Implements retry logic with exponential backoff:
        - Retry delays: 1, 2, 4, 8, 16, 32 seconds
        - Total of 6 retry attempts
        
        Args:
            evaluation_url: Evaluation API endpoint
            result: Deployment result data
            
        Returns:
            bool: True if notification successful, False otherwise
        """
        delays = [1, 2, 4, 8, 16, 32]
        
        for i, delay in enumerate(delays + [0]):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        evaluation_url,
                        headers={"Content-Type": "application/json"},
                        json=result
                    )
                    
                    if response.status_code == 200:
                        print(f"[OK] Evaluation notification successful")
                        return True
                    else:
                        print(f"[FAIL] Evaluation notification failed: {response.status_code}, {response.text}")
                        
            except Exception as e:
                print(f"[ERROR] Evaluation notification error: {e}")

            # Wait before retry (except on last attempt)
            if i < len(delays):
                print(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        
        return False

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Initialize deployment manager (singleton pattern)
deployment_manager = DeploymentManager()

# ============================================================================
# FASTAPI ENDPOINTS
# ============================================================================
@app.post("/api-endpoint")
async def handle_task(request: Request):
    """
    Main API endpoint that receives task requests from instructors.
    
    Validates request credentials and processes deployment asynchronously.
    Returns immediate HTTP 200 response while deployment runs in background.
    
    Request body must include:
    - email: Student email (must match STUDENT_EMAIL)
    - secret: Authentication secret (must match STUDENT_SECRET)
    - task: Unique task identifier
    - round: Round number (1 or 2)
    - nonce: Unique nonce for this request
    - brief: Task description
    - checks: List of evaluation checks
    - evaluation_url: URL to notify with results
    - attachments: List of file attachments (optional)
    
    Returns:
        JSONResponse: Immediate acknowledgment with task info
        
    Raises:
        HTTPException: If authentication fails (401) or other errors (500)
    """    
    try:
        # Parse JSON request body
        task_data = await request.json()

        # Validate secret matches configured value
        if task_data.get('secret') != STUDENT_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")

        # Validate email matches configured value
        if task_data.get('email') != STUDENT_EMAIL:
            raise HTTPException(status_code=401, detail="Invalid email")

        # Prepare immediate response
        response_data = {
            "status": "received", 
            "task": task_data.get('task'),
            "round": task_data.get('round', 1)
        }

        # Process deployment asynchronously in background
        # This allows us to return HTTP 200 immediately
        asyncio.create_task(process_deployment(task_data))
        
        return JSONResponse(content=response_data, status_code=200)
        
    except Exception as e:
        print(f"Error handling request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_deployment(task_data: Dict):
    """
    Background task that handles complete deployment workflow.
    
    Executes asynchronously after returning HTTP 200 to client.
    
    Workflow:
    1. Deploy application (generate code, create repo, enable Pages)
    2. Notify evaluation API with results
    3. Log success or failure
    
    Args:
        task_data: Complete task request data
    """
    try:
        # Log start of deployment
        print(f"\n{'='*60}")
        print(f"Processing task: {task_data.get('task')} - Round {task_data.get('round', 1)}")
        print(f"{'='*60}\n")

        # Execute deployment workflow
        result = await deployment_manager.deploy(task_data)

        # Log deployment success
        print(f"\n[OK] Deployment complete!")
        print(f"  Repo: {result['repo_url']}")
        print(f"  Pages: {result['pages_url']}")
        print(f"  Commit: {result['commit_sha'][:8]}")

        # Notify evaluation API with results
        evaluation_url = task_data.get('evaluation_url')
        if evaluation_url:
            print(f"\nNotifying evaluation API...")
            success = await deployment_manager.notify_evaluation(evaluation_url, result)
            if success:
                print(f"[OK] Evaluation notified successfully")
            else:
                print(f"[FAIL] Failed to notify evaluation API")
        
        print(f"\n{'='*60}\n")
        
    except Exception as e:
        # Log deployment failure with full traceback
        print(f"\n[ERROR] DEPLOYMENT ERROR: {e}")
        import traceback
        traceback.print_exc()

@app.get("/")
async def root():
    """
    Root endpoint - Basic health check and system information.
    
    Returns system status, configuration, and supported features.
    
    Returns:
        dict: System information including:
            - status: Current running status
            - service: Service name
            - API: LLM API provider
            - model: Current LLM model in use
            - supported_models: List of available models
            - email: Configured student email
            - github_configured: Whether GitHub token is set
            - llm_configured: Whether LLM API key is set
    """
    return {
        "status": "running",
        "service": "LLM Code Deployment System",
        "API": "AIpipe OpenRouter",
        "model": AIPIPE_MODEL,
        "supported_models": [
            "openai/gpt-4.1",
            "anthropic/claude-sonnet-4.5"
        ],
        "email": STUDENT_EMAIL,
        "github_configured": bool(GITHUB_TOKEN),
        "llm_configured": bool(AIPIPE_API_KEY)
    }

@app.get("/health")
async def health():
    """
    Detailed health check endpoint.
    
    Provides comprehensive system configuration status for debugging.
    
    Returns:
        dict: Detailed health information including:
            - api_endpoint: Main API endpoint path
            - environment: Configuration status of all env variables
                - github_token: Whether GitHub token is configured
                - aipipe_key: Whether AIpipe API key is configured
                - aipipe_url: Current AIpipe API URL
                - aipipe_model: Current LLM model selection
                - student_email: Configured email
                - student_secret: Whether secret is configured
    """
    return {
        "api_endpoint": "/api-endpoint",
        "environment": {
            "github_token": "configured" if GITHUB_TOKEN else "missing",
            "aipipe_key": "configured" if AIPIPE_API_KEY else "missing",
            "aipipe_url": AIPIPE_API_URL,
            "aipipe_model": AIPIPE_MODEL,
            "student_email": STUDENT_EMAIL or "missing",
            "student_secret": "configured" if STUDENT_SECRET else "missing"
        }
    }

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    """
    Run the FastAPI application using Uvicorn ASGI server.
    
    Configuration:
    - Host: 0.0.0.0 (accessible from all network interfaces)
    - Port: 7860 (Hugging Face Spaces default port)
    """
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)