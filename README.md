# LLM Code Deployment System

An automated, production-grade deployment platform that generates complete web applications from task briefs using large language models, creates GitHub repositories, enables GitHub Pages hosting, and integrates with evaluation systems.

## Overview

This system orchestrates a sophisticated workflow that transforms high-level task descriptions into fully functional, deployed web applications. By leveraging LLM capabilities (OpenAI GPT-4.1 or Anthropic Claude Sonnet 4.5) through the AIpipe OpenRouter API, it generates complete HTML/CSS/JavaScript applications, manages GitHub repository operations, deploys to GitHub Pages, and notifies external evaluation systems.

The system supports iterative development through a two-round evaluation cycle, allowing applications to be enhanced based on initial feedback.

## Key Features

**Intelligent Code Generation**
- Leverages state-of-the-art LLMs to generate complete, production-ready web applications
- Automatically handles multiple file types: HTML with embedded CSS/JavaScript, README documentation, and MIT License files
- Supports attachment processing for CSV, JSON, Markdown, and binary data files
- Implements intelligent fallback logic: if Claude Sonnet 4.5 fails, automatically retries with GPT-4.1
- Configurable model selection for balancing cost and quality

**GitHub Repository Management**
- Automated repository creation with proper initialization
- Atomic file upload and update operations using GitHub API
- SHA-based file management for reliable updates during Round 2 revisions
- Verification that repositories exist before processing updates
- Automatic GitHub Pages enablement from repository root

**Deployment Verification**
- Robust polling mechanism to verify GitHub Pages deployment completion
- Up to 3 minutes of verification attempts with 10-second intervals
- Clear logging of deployment status and troubleshooting information
- Graceful handling of edge cases and network delays

**Two-Round Evaluation Cycle**
- Round 1: Generate and deploy new applications from task briefs
- Round 2: Update existing applications with enhancements and improvements
- Automatic validation that Round 2 updates target existing repositories
- Clear documentation markers indicating Round 2 updates in README files

**External System Integration**
- RESTful API for receiving task requests from instructors or task management systems
- Asynchronous background processing to provide immediate HTTP 200 responses
- Retry logic with exponential backoff for reliability (6 attempts with delays: 1, 2, 4, 8, 16, 32 seconds)
- Secure request validation using email and secret authentication
- Detailed result notification including repository URL, commit SHA, and Pages URL

**Development and Deployment Options**
- Containerized deployment with Docker for cloud platforms
- Compatible with Hugging Face Spaces (port 7860 by default)
- Support for standard Python virtual environments
- Comprehensive logging and debugging endpoints

## System Architecture

### Core Components

**LLMClient**
Manages all communication with the AIpipe OpenRouter API. Handles:
- OpenAI-compatible API formatting
- Model selection and switching
- Automatic fallback from Claude to GPT-4.1 on failure
- Configurable token limits and temperature for response consistency

**GitHubManager**
Abstracts all GitHub REST API operations. Provides:
- Repository existence checking
- Repository creation with metadata
- File upload/update with SHA verification
- GitHub Pages enablement
- GitHub Pages live deployment verification
- Authenticated user information retrieval

**AttachmentProcessor**
Processes data URIs and file attachments. Supports:
- Base64 decoding of data URIs
- Text content extraction for CSV, JSON, Markdown, and plain text files
- Preservation of binary file metadata
- Efficient handling of large files

**CodeGenerator**
Orchestrates LLM-based application generation. Handles:
- Construction of detailed prompts incorporating briefs, checks, and attachments
- LLM response parsing using regex-based file extraction
- MIT License generation with current year
- Support for multiple file extraction formats (delimiters and code blocks)

**DeploymentManager**
Coordinates the complete workflow. Manages:
- Sequential execution of generation, repository management, and deployment
- Round 1 vs Round 2 workflow differentiation
- Deployment result compilation
- Evaluation system notification with retry logic

### Request/Response Flow

```
1. Task Request → API Endpoint (/api-endpoint)
2. Authentication Validation (email, secret)
3. Immediate HTTP 200 Response
4. Background Processing:
   a. LLM generates complete application code
   b. Repository created (Round 1) or verified (Round 2)
   c. Files uploaded: index.html, README.md, LICENSE
   d. GitHub Pages enabled
   e. Deployment verification polling
   f. Evaluation API notification with results
```

## Installation

### Prerequisites

- Python 3.10 or higher
- GitHub Personal Access Token (fine-grained permissions)
- AIpipe OpenRouter API key
- Valid GitHub account

### Standard Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd llm-code-deployment
```

2. Create a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables (see Configuration section below)

5. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:7860`

### Docker Installation

1. Build the Docker image:
```bash
docker build -t llm-deployment-system .
```

2. Run the container with environment variables:
```bash
docker run -p 7860:7860 \
  -e AIPIPE_API_URL="your_api_url" \
  -e AIPIPE_API_KEY="your_api_key" \
  -e GITHUB_TOKEN="your_github_token" \
  -e STUDENT_EMAIL="your_email" \
  -e STUDENT_SECRET="your_secret" \
  llm-deployment-system
```

### Hugging Face Spaces Deployment

1. Create a new Space on Hugging Face
2. Choose Docker as the runtime environment
3. Upload `Dockerfile`, `app.py`, and `requirements.txt`
4. Set environment variables in Space settings:
   - `AIPIPE_API_URL`
   - `AIPIPE_API_KEY`
   - `GITHUB_TOKEN`
   - `STUDENT_EMAIL`
   - `STUDENT_SECRET`
5. The Space will automatically build and deploy

## Configuration

### Environment Variables

All configuration is handled through environment variables. No code modifications are required.

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `AIPIPE_API_URL` | Yes | AIpipe OpenRouter API endpoint | `https://api.openrouter.com/api/v1/chat/completions` |
| `AIPIPE_API_KEY` | Yes | Authentication key for AIpipe | (API key from AIpipe) |
| `AIPIPE_MODEL` | No | LLM model selection | `openai/gpt-4.1` or `anthropic/claude-sonnet-4.5` |
| `GITHUB_TOKEN` | Yes | GitHub Personal Access Token | (Fine-grained token with repo access) |
| `STUDENT_EMAIL` | Yes | Authorized email for API requests | `student@university.edu` |
| `STUDENT_SECRET` | Yes | Secret for request authentication | (Any secure random string) |

### Model Selection

The system supports two models via AIpipe OpenRouter:

**OpenAI GPT-4.1** (Default)
- Faster response times
- Lower computational cost
- Good code quality
- Suitable for most use cases
- Automatically used as fallback if Claude fails

**Anthropic Claude Sonnet 4.5**
- Excellent code quality
- Superior reasoning capabilities
- Longer processing time
- Higher token costs
- Falls back to GPT-4.1 on failure

### GitHub Token Setup

Generate a fine-grained Personal Access Token:

1. Go to GitHub Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
2. Click "Generate new token"
3. Configure permissions:
   - Repository access: All repositories
   - Permissions required:
     - `Contents: Read and Write` (for file uploads)
     - `Pages: Read and Write` (for enabling Pages)
     - `Metadata: Read` (for repository information)
4. Set expiration as needed
5. Copy the token and set as `GITHUB_TOKEN`

## API Reference

### Main Endpoint: POST /api-endpoint

Receives task briefs and initiates the deployment workflow.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "student@university.edu",
  "secret": "your_configured_secret",
  "task": "unique_task_identifier",
  "round": 1,
  "nonce": "unique_request_nonce",
  "brief": "Complete task description and requirements",
  "checks": [
    "Application must support user input",
    "Data must persist during session",
    "UI must be responsive"
  ],
  "evaluation_url": "https://evaluator.example.com/notify",
  "attachments": [
    {
      "name": "data.csv",
      "url": "data:text/csv;base64,..."
    }
  ]
}
```

**Response (Immediate):**
```json
{
  "status": "received",
  "task": "unique_task_identifier",
  "round": 1
}
```

**Background Workflow Result (Sent to evaluation_url):**
```json
{
  "email": "student@university.edu",
  "task": "unique_task_identifier",
  "round": 1,
  "nonce": "unique_request_nonce",
  "repo_url": "https://github.com/username/unique_task_identifier",
  "commit_sha": "abc1234567890def",
  "pages_url": "https://username.github.io/unique_task_identifier/"
}
```

### Health Check Endpoints

**GET /** - System Status
```json
{
  "status": "running",
  "service": "LLM Code Deployment System",
  "API": "AIpipe OpenRouter",
  "model": "openai/gpt-4.1",
  "supported_models": ["openai/gpt-4.1", "anthropic/claude-sonnet-4.5"],
  "email": "configured_email@example.com",
  "github_configured": true,
  "llm_configured": true
}
```

**GET /health** - Detailed Configuration Status
```json
{
  "api_endpoint": "/api-endpoint",
  "environment": {
    "github_token": "configured",
    "aipipe_key": "configured",
    "aipipe_url": "https://api.openrouter.com/...",
    "aipipe_model": "openai/gpt-4.1",
    "student_email": "student@university.edu",
    "student_secret": "configured"
  }
}
```

## Usage Examples

### Example 1: Basic Task Deployment

```bash
curl -X POST http://localhost:7860/api-endpoint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@university.edu",
    "secret": "your_secret",
    "task": "todo_app",
    "round": 1,
    "nonce": "abc123",
    "brief": "Create a todo list application with add, delete, and mark complete features",
    "checks": [
      "Users can add new todos",
      "Users can delete todos",
      "Users can mark todos as complete",
      "Todos persist during session"
    ],
    "evaluation_url": "https://evaluator.example.com/notify"
  }'
```

### Example 2: Round 2 Enhancement

```bash
curl -X POST http://localhost:7860/api-endpoint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@university.edu",
    "secret": "your_secret",
    "task": "todo_app",
    "round": 2,
    "nonce": "def456",
    "brief": "Enhance the todo app with due dates, priority levels, and filtering capabilities",
    "checks": [
      "Todos support due date assignment",
      "Priority levels (high/medium/low) can be set",
      "Users can filter by priority",
      "Existing functionality still works"
    ],
    "evaluation_url": "https://evaluator.example.com/notify"
  }'
```

### Example 3: Task with Data Attachment

First, convert your CSV/JSON file to base64:
```bash
base64 -w 0 data.csv
```

Then include in request:
```bash
curl -X POST http://localhost:7860/api-endpoint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@university.edu",
    "secret": "your_secret",
    "task": "data_dashboard",
    "round": 1,
    "nonce": "ghi789",
    "brief": "Create a dashboard to visualize the provided sales data",
    "checks": ["Dashboard displays all data points", "Charts are interactive"],
    "evaluation_url": "https://evaluator.example.com/notify",
    "attachments": [
      {
        "name": "sales_data.csv",
        "url": "data:text/csv;base64,TmFtZSxSZWdpb24sU2FsZXM=..."
      }
    ]
  }'
```

## Error Handling

### Authentication Errors (401)

- **Invalid Secret**: Ensure `secret` matches `STUDENT_SECRET` environment variable
- **Invalid Email**: Ensure `email` matches `STUDENT_EMAIL` environment variable

Verify configuration:
```bash
curl http://localhost:7860/health
```

### Deployment Failures

Common issues and solutions:

| Issue | Cause | Solution |
|-------|-------|----------|
| "Round 2 request but repo doesn't exist" | Requesting Round 2 for non-existent repo | Verify task name matches Round 1 deployment |
| GitHub API errors | Token expired or insufficient permissions | Regenerate GitHub token with correct permissions |
| LLM generation timeout | Model request took too long | Check AIpipe API status; consider GPT-4.1 model |
| Pages verification timeout | GitHub delayed in processing | Pages is deployed but took >3 minutes; content is live |

### Debugging

Enable detailed logging:
1. Check the application logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test GitHub token: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user`
4. Test AIpipe API connectivity and authentication

## Supported Features and Limitations

### Supported

- Single-page applications (SPAs) with embedded CSS/JavaScript
- CSV and JSON data file processing
- Markdown documentation generation
- GitHub Pages static site hosting
- Two-round iterative development cycle
- Asynchronous task processing with immediate responses
- Automatic model fallback for reliability
- Custom attachment data via data URIs

### Limitations

- No server-side backend support (GitHub Pages is static-only)
- No database persistence (session-based storage only via JavaScript)
- Maximum response time per LLM request: 180 seconds
- Single-page applications only (not multi-page sites)
- No support for private repositories

## Performance Considerations

### Response Times

- **LLM Generation**: 15-120 seconds (depending on model and complexity)
- **GitHub Repository Operations**: 2-5 seconds
- **GitHub Pages Deployment**: 30-180 seconds (verification polling)
- **Total End-to-End**: 1-5 minutes typical

### Rate Limiting

- GitHub API: 5,000 requests/hour per token
- AIpipe OpenRouter: Subject to provider limits (typically 100-1000 requests/day depending on plan)
- Evaluation notification: Exponential backoff with 6 retry attempts

### Scalability

The system uses async/await throughout for efficient resource utilization. It can handle multiple concurrent deployments limited by:
- AIpipe API rate limits
- GitHub API rate limits
- Server memory for buffering LLM responses

For production deployment at scale, consider:
- Running multiple instances behind a load balancer
- Implementing request queuing for rate limit management
- Using GitHub Organization tokens for higher rate limits

## Security Considerations

### Authentication

- Email-based verification for API requests
- Shared secret validation
- No sensitive data in logs or error messages

### GitHub Token Security

- Use fine-grained Personal Access Tokens (not classic tokens)
- Restrict token to necessary repositories
- Set token expiration dates
- Regularly rotate tokens

### Data Handling

- File attachments handled as data URIs (base64 encoded)
- No data stored on server (stateless design)
- All operations logged for audit trails

### Best Practices

1. Use strong, randomly-generated secrets for `STUDENT_SECRET`
2. Rotate GitHub tokens periodically
3. Monitor logs for unauthorized access attempts
4. Use HTTPS for all API communication
5. Restrict API endpoint access by IP if possible

## Troubleshooting

### Common Issues

**Issue: "Invalid secret" or "Invalid email"**
- Verify environment variables are set correctly
- Check the `/health` endpoint to see configured values
- Ensure request JSON exactly matches configured email

**Issue: Repository creation fails**
- Verify GitHub token has correct permissions
- Check GitHub API status page
- Ensure token hasn't expired

**Issue: LLM generation fails**
- Check AIpipe API status and credentials
- Verify `AIPIPE_API_URL` and `AIPIPE_API_KEY` are correct
- System will automatically retry with GPT-4.1 if Claude fails

**Issue: GitHub Pages not accessible after deployment**
- Pages deployment takes 1-3 minutes after repository creation
- The system polls for up to 3 minutes; if timeout occurs, pages are likely still deploying
- Check the GitHub repository settings to verify Pages is enabled
- Try accessing the pages URL after a few minutes

**Issue: Evaluation API notification never received**
- Verify `evaluation_url` is publicly accessible
- Check server logs for retry attempts
- System retries up to 6 times with exponential backoff (up to 32 seconds between attempts)

## Development and Contributing

### Code Structure

```
llm-code-deployment/
├── app.py              # Main FastAPI application
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration
└── README.md          # This file
```

### Key Classes

- `LLMClient`: Handles LLM API communication
- `GitHubManager`: Manages GitHub REST API operations
- `AttachmentProcessor`: Processes file attachments
- `CodeGenerator`: Orchestrates code generation
- `DeploymentManager`: Coordinates complete workflow

### Extending the System

To add new features:

1. **New LLM Models**: Update `LLMClient.supported_models` and add to `AIPIPE_MODEL` options
2. **New File Types**: Extend `CodeGenerator._parse_response()` for additional file formats
3. **Enhanced Attachments**: Modify `AttachmentProcessor` for additional MIME types
4. **Custom Notifications**: Override `DeploymentManager.notify_evaluation()` for new systems

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.119.0 | Web framework |
| uvicorn | 0.37.0 | ASGI server |
| httpx | 0.28.1 | Async HTTP client |
| python-multipart | 0.0.20 | Multipart form support |

All dependencies are pinned to specific versions for reproducibility.

## License

MIT License - See LICENSE file for details

## Support and Contact

For issues, questions, or contributions:
- Review the Troubleshooting section above
- Check logs on the `/health` endpoint
- Consult the API Reference for correct request formats

## Changelog

### Version 1.0.0
- Initial release
- LLM-based code generation via AIpipe OpenRouter
- GitHub repository and Pages management
- Two-round evaluation cycle support
- Attachment processing for CSV, JSON, Markdown files
- Comprehensive error handling and logging
