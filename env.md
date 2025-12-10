# Configuration Best Practices

## Why Not Hardcode .env?

1. **Multiple Environments**: Dev, staging, production need different configs
2. **CI/CD**: Build systems may not have .env files
3. **Docker/Kubernetes**: Use environment variables directly
4. **Security**: Production secrets shouldn't be in .env files in repo

## Configuration Priority (Highest to Lowest)

1. **System Environment Variables** (best for production)
2. **Environment-specific .env file** (.env.production, .env.staging)
3. **Default .env file** (local development)
4. **Hardcoded defaults** (fallback values)

## Usage Patterns

### Pattern 1: Local Development
```bash
# Use default .env file
python your_script.py
```

### Pattern 2: Specify Environment
```bash
# Set ENV variable to load .env.{ENV}
export ENV=production
python your_script.py  # loads .env.production
```

### Pattern 3: Explicit File
```python
from config import load_config

# Load specific file
config = load_config(".env.staging")
```

### Pattern 4: System Environment (Production)
```bash
# No .env file needed - use system env vars
export POLYMARKET_PRIVATE_KEY=abc123...
export POLYMARKET_SIGNATURE_TYPE=0
python your_script.py
```

### Pattern 5: Docker/Kubernetes
```yaml
# docker-compose.yml
services:
  app:
    environment:
      - POLYMARKET_PRIVATE_KEY=${PRIVATE_KEY}
      - POLYMARKET_SIGNATURE_TYPE=0
```

## Security Best Practices

1. **Never commit .env files** - Add to .gitignore
2. **Use .env.example** - Template without secrets
3. **Production secrets** - Use AWS Secrets Manager, HashiCorp Vault, or K8s secrets
4. **Rotate keys regularly**
5. **Use env prefixes** - Avoid collisions (POLYMARKET_* vs APP_*)

## File Structure
```
your_project/
├── .env                    # Local dev (gitignored)
├── .env.example           # Template (committed)
├── .env.development       # Dev environment (gitignored)
├── .env.staging          # Staging (gitignored)
├── .env.production       # Production (gitignored)
├── .gitignore            # Ignore all .env except .env.example
└── config.py             # Configuration loader
```

## .gitignore
```
.env
.env.*
!.env.example
```