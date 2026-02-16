# Kiyanshi Organics - Production Deployment Guide

## 📋 Prerequisites

- A VPS/Server with at least 1GB RAM
- Docker and Docker Compose installed
- Domain name (optional, for custom domain)
- SSH access to your server

## 🚀 Quick Start - Free Deployment Options

### Option 1: Railway.app (Recommended - Easiest)
**Free Tier**: 500 hours/month, $5 credit

1. Create account at https://railway.app
2. Install Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```
3. Login and initialize:
   ```bash
   railway login
   railway init
   ```
4. Deploy:
   ```bash
   railway up
   ```
5. Set environment variables in Railway dashboard
6. Get your app URL from Railway dashboard

### Option 2: Render.com
**Free Tier**: 750 hours/month

1. Push code to GitHub
2. Go to https://render.com and sign up
3. Create new "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && gunicorn --bind 0.0.0.0:$PORT app:app`
6. Add environment variables in Render dashboard
7. Create another Web Service for frontend (Static Site)

### Option 3: Fly.io
**Free Tier**: 3 VMs, 3GB storage

1. Install flyctl:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
2. Login:
   ```bash
   flyctl auth login
   ```
3. Create fly.toml (see below)
4. Deploy:
   ```bash
   flyctl launch
   flyctl deploy
   ```

### Option 4: Oracle Cloud (Best for India)
**Free Tier**: 2 VMs (1 GB RAM each), Always Free

1. Create account at https://www.oracle.com/cloud/free/
2. Create a VM instance (Ubuntu)
3. SSH into server
4. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```
5. Install Docker Compose:
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```
6. Clone your repository and follow "Manual Docker Deployment" below

## 🔧 Manual Docker Deployment (Any VPS)

### 1. Prepare Your Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again for docker group to take effect
```

### 2. Clone Your Repository

```bash
cd /home/$USER
git clone https://github.com/yourusername/kiyanshi_organics_prod.git
cd kiyanshi_organics_prod
```

### 3. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit with your values
nano .env
```

**Important Variables to Change:**
```env
SECRET_KEY=generate-a-long-random-string-here
ADMIN_MOBILE=your-admin-mobile-number
ALLOWED_ORIGINS=http://your-domain.com,https://your-domain.com
```

Generate a secure SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Update Frontend API URL

Edit all HTML files in `frontend/` folder and update the API URL:
```javascript
// Change this:
const API_URL = 'http://localhost:5000';

// To this:
const API_URL = 'http://your-domain.com/api';
// or
const API_URL = 'http://your-server-ip/api';
```

### 5. Build and Start Services

```bash
# Build images
docker-compose build

# Start services in background
docker-compose up -d

# Check if everything is running
docker-compose ps

# View logs
docker-compose logs -f
```

### 6. Configure Firewall

```bash
# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS (if using SSL)
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

### 7. Test Your Deployment

```bash
# Check health endpoint
curl http://localhost/health

# Check API
curl http://localhost/api/health

# Check frontend
curl http://localhost/
```

## 🔒 Adding SSL/HTTPS (Recommended)

### Using Certbot (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate (make sure port 80 is open and domain points to your server)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is set up automatically
# Test renewal
sudo certbot renew --dry-run
```

### Update Nginx Configuration for HTTPS

Create `nginx/default.conf` with SSL:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Rest of your nginx config...
}
```

## 📊 Monitoring and Maintenance

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Update Application
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### Backup Database
```bash
# Create backup
docker-compose exec backend sqlite3 /app/data/users.db ".backup /app/data/backup_$(date +%Y%m%d).db"

# Copy to host
docker cp kiyanshi_backend:/app/data/backup_$(date +%Y%m%d).db ./backups/
```

### Stop Everything
```bash
docker-compose down

# Stop and remove volumes (WARNING: deletes database)
docker-compose down -v
```

## 🎯 Best Free Options Comparison

| Platform | Free Tier | Pros | Cons | Best For |
|----------|-----------|------|------|----------|
| **Railway** | 500hrs/month | Easiest, auto-deploy from Git | Limited hours | Small projects |
| **Render** | 750hrs/month | Good docs, easy SSL | Sleeps after inactivity | Medium projects |
| **Fly.io** | 3 VMs | Good performance, global | Steeper learning curve | Production-ready |
| **Oracle Cloud** | Always Free 2 VMs | Best specs, no time limit | Complex setup | Long-term projects |

## 🔐 Security Checklist

- ✅ Change default SECRET_KEY
- ✅ Change ADMIN_MOBILE
- ✅ Enable firewall (ufw)
- ✅ Use HTTPS/SSL
- ✅ Regular backups
- ✅ Update ALLOWED_ORIGINS to your domain
- ✅ Keep Docker images updated
- ✅ Monitor logs regularly
- ✅ Use strong passwords
- ✅ Limit database file permissions

## 🆘 Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Port 5000 already in use
# 2. Database permission issues
# 3. Missing environment variables
```

### Frontend can't connect to backend
```bash
# Check if backend is running
docker-compose ps

# Check API_URL in frontend HTML files
# Should be: http://your-domain.com/api or http://your-server-ip/api
```

### Database errors
```bash
# Check database file permissions
ls -la data/

# Reset database (WARNING: deletes all data)
rm data/users.db
docker-compose restart backend
```

## 📞 Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Verify environment variables
3. Check firewall rules
4. Test endpoints individually

## 🎉 Your App is Live!

Access your application at:
- Frontend: `http://your-domain.com` or `http://your-server-ip`
- API Health: `http://your-domain.com/api/health`
- Admin Panel: Login with your ADMIN_MOBILE number

**Important**: On first deployment, add some products using the admin panel before customers can place orders!
