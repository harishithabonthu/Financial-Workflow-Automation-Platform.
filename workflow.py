name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: workflow_db_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

    env:
      DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/workflow_db_test
      SECRET_KEY: ci_test_secret_key
      ENV: development

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Lint (flake8)
        run: |
          pip install flake8
          flake8 app --max-line-length=120 --extend-ignore=E203,W503

      - name: Run tests
        run: pytest -v --tb=short

  build-and-push:
    name: Build & Push Docker Image
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy
    needs: build-and-push
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Deploy notice
        run: |
          echo "Image ghcr.io/${{ github.repository }}:${{ github.sha }} is built and pushed."
          echo "Plug in your deployment step here (e.g. SSH + docker compose pull && up -d,"
          echo "a Kubernetes rollout, or a cloud provider's CLI deploy action)."
      # Example (uncomment and configure for your host):
      # - name: Deploy over SSH
      #   uses: appleboy/ssh-action@v1.0.3
      #   with:
      #     host: ${{ secrets.DEPLOY_HOST }}
      #     username: ${{ secrets.DEPLOY_USER }}
      #     key: ${{ secrets.DEPLOY_SSH_KEY }}
      #     script: |
      #       cd /opt/financial-workflow-platform
      #       docker compose pull
      #       docker compose up -d
