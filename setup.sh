#!/bin/bash

# Kiyanshi Organics - Quick Setup Script
# This script helps you prepare your app for production deployment

set -e  # Exit on error

echo "🌿 Kiyanshi Organics - Production Setup"
echo "========================================"
echo ""

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    
    # Generate SECRET_KEY
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    
    # Update SECRET_KEY in .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/your-secret-key-change-this-in-production/$SECRET_KEY/" .env
    else
        sed -i "s/your-secret-key-change-this-in-production/$SECRET_KEY/" .env
    fi
    
    echo "✅ .env file created with auto-generated SECRET_KEY"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and update:"
    echo "   - ADMIN_MOBILE (your admin phone number)"
    echo "   - ALLOWED_ORIGINS (your domain)"
    echo ""
else
    echo "✅ .env file already exists"
    echo ""
fi

# Ask user for deployment type
echo "📦 What type of deployment do you want?"
echo "1) Local development (Docker Compose)"
echo "2) Production VPS deployment (Docker Compose)"
echo "3) Railway.app (PaaS)"
echo "4) Render.com (PaaS)"
echo "5) Fly.io (PaaS)"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting local development environment..."
        echo ""
        
        # Check if frontend API URL needs updating
        if grep -q "localhost:5000" frontend/customer.html; then
            echo "⚠️  Frontend is configured for direct backend access (localhost:5000)"
            echo "   For Docker Compose, it should use: http://localhost/api"
            echo ""
            read -p "Update frontend API URLs? (y/n): " update_urls
            
            if [ "$update_urls" = "y" ]; then
                echo "Updating API URLs..."
                for file in frontend/*.html; do
                    if [[ "$OSTYPE" == "darwin"* ]]; then
                        sed -i '' 's|http://localhost:5000|http://localhost/api|g' "$file"
                    else
                        sed -i 's|http://localhost:5000|http://localhost/api|g' "$file"
                    fi
                done
                echo "✅ API URLs updated"
            fi
        fi
        
        docker-compose up --build
        ;;
        
    2)
        echo ""
        echo "🌐 Production VPS Deployment Setup"
        echo ""
        read -p "Enter your domain or server IP: " server_address
        
        echo ""
        echo "Updating frontend API URLs to: http://$server_address/api"
        
        for file in frontend/*.html; do
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|const API_URL = '.*'|const API_URL = 'http://$server_address/api'|g" "$file"
            else
                sed -i "s|const API_URL = '.*'|const API_URL = 'http://$server_address/api'|g" "$file"
            fi
        done
        
        echo "✅ Frontend API URLs updated"
        echo ""
        echo "📝 Next steps:"
        echo "1. Edit .env file and set:"
        echo "   - ADMIN_MOBILE"
        echo "   - ALLOWED_ORIGINS=http://$server_address,https://$server_address"
        echo ""
        echo "2. Copy project to your server:"
        echo "   scp -r ./ user@$server_address:/home/user/kiyanshi_organics_prod/"
        echo ""
        echo "3. SSH into server and run:"
        echo "   cd /home/user/kiyanshi_organics_prod"
        echo "   docker-compose up --build -d"
        echo ""
        echo "4. Configure firewall:"
        echo "   sudo ufw allow 80/tcp"
        echo "   sudo ufw allow 443/tcp"
        echo ""
        echo "See DEPLOYMENT.md for detailed instructions"
        ;;
        
    3)
        echo ""
        echo "🚂 Railway.app Deployment"
        echo ""
        echo "📝 Steps:"
        echo "1. Install Railway CLI:"
        echo "   npm install -g @railway/cli"
        echo ""
        echo "2. Login and initialize:"
        echo "   railway login"
        echo "   railway init"
        echo ""
        echo "3. Set environment variables:"
        echo "   railway variables set SECRET_KEY=\$(openssl rand -hex 32)"
        echo "   railway variables set ADMIN_MOBILE=your_mobile"
        echo "   railway variables set ALLOWED_ORIGINS='*'"
        echo ""
        echo "4. Deploy:"
        echo "   railway up"
        echo ""
        echo "See DEPLOYMENT.md for detailed instructions"
        ;;
        
    4)
        echo ""
        echo "🎨 Render.com Deployment"
        echo ""
        echo "📝 Steps:"
        echo "1. Push code to GitHub"
        echo "2. Go to https://render.com and create account"
        echo "3. Create new Web Service from your repo"
        echo "4. Configure environment variables in Render dashboard"
        echo "5. Deploy!"
        echo ""
        echo "A render.yaml file is included for easy setup"
        echo "See DEPLOYMENT.md for detailed instructions"
        ;;
        
    5)
        echo ""
        echo "🚀 Fly.io Deployment"
        echo ""
        echo "📝 Steps:"
        echo "1. Install flyctl:"
        echo "   curl -L https://fly.io/install.sh | sh"
        echo ""
        echo "2. Login:"
        echo "   flyctl auth login"
        echo ""
        echo "3. Launch app:"
        echo "   flyctl launch"
        echo ""
        echo "4. Set secrets:"
        echo "   flyctl secrets set SECRET_KEY=\$(openssl rand -hex 32)"
        echo "   flyctl secrets set ADMIN_MOBILE=your_mobile"
        echo ""
        echo "5. Deploy:"
        echo "   flyctl deploy"
        echo ""
        echo "A fly.toml file is included for easy setup"
        echo "See DEPLOYMENT.md for detailed instructions"
        ;;
        
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "✅ Setup complete!"
echo ""
echo "📚 Next steps:"
echo "   - Review DEPLOYMENT.md for detailed deployment instructions"
echo "   - Check PRODUCTION_CHECKLIST.md before going live"
echo "   - Update README.md with your project details"
echo ""
echo "🆘 Need help? Check the troubleshooting section in DEPLOYMENT.md"
