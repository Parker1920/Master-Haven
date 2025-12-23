# Haven UI - Quick Start Guide

This guide explains how to run the Haven UI in both **Development** and **Production** modes.

---

## 🔧 Option 1: Development Mode (Recommended for Making Changes)

Use this mode when you're actively developing and want to see changes instantly.

### Requirements:
- Two terminal windows
- Both servers running simultaneously

### Steps:

**Terminal 1 - Start Backend API Server:**
```bash
cd path\to\Master-Haven
python src\control_room_api.py
```
✅ Server will start on http://127.0.0.1:8000

**Terminal 2 - Start Frontend Dev Server:**
```bash
cd path\to\Master-Haven\Haven-UI
npm run dev
```
✅ Server will start on http://localhost:5173

**Access the Application:**
- Open your browser to: **http://localhost:5173**

### Pros:
- ✅ Instant hot-reload - changes show up immediately
- ✅ No rebuilding required after edits
- ✅ Fast development workflow
- ✅ See errors in real-time

### Cons:
- ❌ Requires two terminal windows
- ❌ Both servers must stay running
- ❌ More complex to share via ngrok (need to expose port 5173)

### Notes:
- The Keeper Discord bot should connect to: `http://127.0.0.1:8000/api/discoveries`
- Frontend automatically proxies `/api` requests to the backend
- Great for testing and development work

---

## 🚀 Option 2: Production Mode (Recommended for Sharing/ngrok)

Use this mode when you're done making changes and want to share the app with others.

### Requirements:
- One terminal window
- Must rebuild after every code change

### Steps:

**Step 1 - Build the Production Bundle:**
```bash
cd path\to\Master-Haven\Haven-UI
npm run build
```
✅ Creates optimized files in `/dist` folder

**Step 2 - Start Backend Server (serves the built app):**
```bash
cd path\to\Master-Haven
python src\control_room_api.py
```
✅ Server will start on http://127.0.0.1:8000

**Step 3 - (Optional) Expose with ngrok:**
```bash
ngrok http 8000
```
✅ Get public URL like: https://abc123.ngrok.io

**Access the Application:**
- Locally: **http://127.0.0.1:8000/haven-ui/**
- Public (ngrok): **https://your-ngrok-url.ngrok.io/haven-ui/**

### Pros:
- ✅ Only one server needed
- ✅ Optimized and minified code
- ✅ Easy to share via ngrok
- ✅ Production-ready performance

### Cons:
- ❌ Must run `npm run build` after EVERY code change
- ❌ Slower development workflow
- ❌ No hot-reload

### Notes:
- The Keeper Discord bot should connect to: `https://your-ngrok-url.ngrok.io/api/discoveries`
- Backend serves both the API and the built React app
- Users access via `/haven-ui/` path

---

## 🤖 Keeper Bot Integration

The Discord Keeper bot only talks to the **Backend API Server** (port 8000).

### Configuration:

**For Local Development:**
```python
# In Keeper bot config
HAVEN_API_URL = "http://127.0.0.1:8000"
```

**For Production/ngrok:**
```python
# In Keeper bot config
HAVEN_API_URL = "https://your-ngrok-url.ngrok.io"
```

The Keeper bot posts discoveries to:
- Endpoint: `POST /api/discoveries`
- Full URL: `{HAVEN_API_URL}/api/discoveries`

---

## 📁 File Structure

```
Master-Haven/
├── src/
│   └── control_room_api.py         # Backend API server (Python/FastAPI)
└── Haven-UI/
    ├── src/                         # React source code
    │   ├── pages/                   # Page components
    │   ├── components/              # Reusable components
    │   └── utils/                   # Utilities and API helpers
    ├── dist/                        # Production build (created by npm run build)
    ├── package.json                 # Node dependencies
    └── vite.config.mjs             # Vite configuration
```

---

## 🔄 Typical Workflow

### During Development:
1. Start both servers (Development Mode)
2. Make changes to React code in `Haven-UI/src/`
3. See changes instantly in browser
4. Repeat until satisfied

### When Ready to Share:
1. Stop dev servers
2. Run `npm run build` in Haven-UI folder
3. Start backend server only
4. Start ngrok tunnel
5. Share ngrok URL with users

### Making More Changes:
1. Switch back to Development Mode
2. Make your edits
3. When done, rebuild and redeploy

---

## 🐛 Troubleshooting

### "Cannot GET /api/systems"
- ✅ Make sure backend server is running on port 8000
- ✅ Check that vite proxy is configured correctly

### "Blank page after npm run build"
- ✅ Check browser console for errors
- ✅ Verify backend is serving `/haven-ui/` path
- ✅ Try accessing `http://127.0.0.1:8000/haven-ui/` directly

### "Changes not showing up"
- **Development Mode:** Wait a few seconds, should auto-reload
- **Production Mode:** Did you run `npm run build` again?

### "Port already in use"
- ✅ Kill existing processes on ports 5173 or 8000
- ✅ Use `Ctrl+C` to stop running servers

---

## 📝 Summary

| Feature | Development Mode | Production Mode |
|---------|-----------------|-----------------|
| **Terminals Needed** | 2 | 1 |
| **Rebuild Required** | No | Yes (after every change) |
| **Hot Reload** | ✅ Yes | ❌ No |
| **ngrok Friendly** | ⚠️ Needs port 5173 | ✅ Yes (port 8000) |
| **Speed** | Fast development | Optimized runtime |
| **Best For** | Making changes | Sharing with users |

---

## 🎯 Quick Command Reference

### Development Mode:
```bash
# Terminal 1
python src\control_room_api.py

# Terminal 2
npm run dev
```

### Production Mode:
```bash
# Build first
npm run build

# Then run
python src\control_room_api.py

# Optional: ngrok
ngrok http 8000
```

---

**Need help?** Check the console output for error messages or contact the development team.

**Last Updated:** November 2025
