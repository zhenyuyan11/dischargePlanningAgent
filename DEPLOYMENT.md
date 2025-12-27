# Deployment Guide: dischargePlanningAgent

## ⚠️ IMPORTANT SECURITY NOTICE

This application handles **Protected Health Information (PHI)**. Before deploying with real patient data:

- **DO NOT** use Streamlit Community Cloud for production with real patient data
- **DO** use HIPAA-compliant hosting (AWS/Azure/GCP with Business Associate Agreement)
- **DO** implement proper authentication and access controls
- **DO** encrypt data at rest and in transit
- **DO** conduct a security audit

The instructions below are for **DEMONSTRATION/TESTING ONLY**.

---

## Option 1: Streamlit Community Cloud (Free - Demo Only)

### Prerequisites
1. GitHub account
2. OpenAI API key

### Step 1: Push Code to GitHub

```bash
# Navigate to your project directory
cd "/Users/zhenyuyan/Documents/Prof Wei"

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - dischargePlanningAgent"

# Create a new repository on GitHub (via web interface)
# Then link it:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Streamlit Community Cloud

1. Go to https://share.streamlit.io
2. Click "New app"
3. Select your GitHub repository
4. Main file path: `streamlit_app.py`
5. Click "Deploy"

### Step 3: Add Secrets

1. In Streamlit Cloud dashboard, click your app
2. Click "Settings" → "Secrets"
3. Add your OpenAI API key:

```toml
OPENAI_API_KEY = "sk-your-actual-api-key-here"
```

4. Save

### Step 4: Access Your App

Your app will be available at:
`https://YOUR_USERNAME-YOUR_REPO_NAME.streamlit.app`

---

## Option 2: HIPAA-Compliant Production Deployment

### Requirements for Production

1. **HIPAA-Compliant Hosting**
   - AWS with BAA (Business Associate Agreement)
   - Azure with BAA
   - Google Cloud with BAA

2. **Database Migration**
   - Replace SQLite with PostgreSQL/MySQL
   - Implement proper database encryption
   - Set up automated backups

3. **Security Enhancements**
   - Implement user authentication (OAuth, SAML)
   - Add role-based access control (RBAC)
   - Enable audit logging
   - Implement data encryption at rest
   - Use HTTPS/TLS for all connections

4. **Compliance**
   - Sign Business Associate Agreement with hosting provider
   - Implement access logs and monitoring
   - Set up data retention policies
   - Create incident response plan

### Recommended Stack

- **Hosting**: AWS ECS or Azure App Service
- **Database**: AWS RDS (PostgreSQL) or Azure Database
- **Secrets**: AWS Secrets Manager or Azure Key Vault
- **Monitoring**: CloudWatch or Azure Monitor
- **Authentication**: AWS Cognito or Azure AD

---

## Database Considerations

### Current Setup (SQLite)
- ✅ Good for: Local development, single user
- ❌ Bad for: Multiple users, cloud deployment

### For Production
Replace SQLite with PostgreSQL:

1. Install PostgreSQL adapter:
```bash
pip install psycopg2-binary
```

2. Update `database.py` to use PostgreSQL connection
3. Set up database connection pooling
4. Implement proper migrations

---

## Environment Variables

### Local Development (.env file)
```
OPENAI_API_KEY=sk-your-api-key
```

### Streamlit Cloud (Secrets)
Add in Streamlit Cloud dashboard under Settings → Secrets

### Production (AWS/Azure)
Use cloud provider's secret management service

---

## Cost Estimates

### Streamlit Community Cloud
- **Hosting**: Free
- **OpenAI API**: ~$60-90/month (100 patients/day)
- **Total**: ~$60-90/month

### HIPAA-Compliant AWS
- **EC2/ECS**: ~$50-100/month
- **RDS (PostgreSQL)**: ~$50-150/month
- **Load Balancer**: ~$20/month
- **Backups/Storage**: ~$20/month
- **OpenAI API**: ~$60-90/month
- **Total**: ~$200-380/month

---

## Post-Deployment Checklist

- [ ] Test all features in deployed environment
- [ ] Verify OpenAI API key works
- [ ] Test PDF generation
- [ ] Verify database persistence
- [ ] Test with multiple users (if applicable)
- [ ] Set up monitoring/alerts
- [ ] Document access URLs and credentials
- [ ] Train users on how to access

---

## Troubleshooting

### App won't start
- Check Streamlit Cloud logs
- Verify requirements.txt has all dependencies
- Ensure secrets are configured

### Database errors
- SQLite won't persist data on Streamlit Cloud (files reset on restart)
- Solution: Use external database (PostgreSQL on Heroku/Supabase)

### OpenAI API errors
- Verify API key is correct in secrets
- Check API quota/billing

---

## Support

For deployment issues:
- Streamlit Community: https://discuss.streamlit.io
- Documentation: https://docs.streamlit.io/streamlit-community-cloud

For HIPAA compliance consultation:
- Consult with healthcare IT security professionals
- Work with legal team for compliance requirements
