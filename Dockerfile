# استخدم الصورة الرسمية من Microsoft لـ Playwright مع Python – دي جاهزة تمام ومش بتحتاج تثبيت deps يدوي
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

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
