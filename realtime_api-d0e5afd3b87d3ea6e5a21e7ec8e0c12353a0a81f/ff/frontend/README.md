
# Openai Realtime API

![alt_text](/ff/frontend/public/pic.png)

## React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

More UI implementation for interface is yet to be done

## Backend

Create a Virtual environment and navigate to backend/requirements.txt and run Pip install -r requirements.txt

Navigate to realtime_api-d0e5afd3b87d3ea6e5a21e7ec8e0c12353a0a81f/backend and run:

uvicorn main:app --host 0.0.0.0 --port 8000

You should see this below in your terminal

INFO:     Started server process [190092]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on port [8000](http://0.0.0.0:8000) (Press CTRL+C to quit)
^CINFO:     Shutting down
INFO:root:Frontend WebSocket disconnected
INFO:     connection closed
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [240890]
INFO:     Stopping reloader process [238400]

## Frontend

Install package. json at  ff/frontend/package.json using npm install  and navigate to  /ff/frontend  and run "npm run dev"

![alt_text](/ff/frontend/public/pica.png)

Created by [Adesoji](https://www.github.com/Adesoji1)

## Further Work

Deployment to Kubernetes Cluster using Rancher, dockerization and Monitoring 