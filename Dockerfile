# الصورة الرسمية من Microsoft لـ Playwright مع Python – جاهزة تمام (Chromium + deps كلها مثبتة)
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port", "$PORT", "--server.headless", "true"]
