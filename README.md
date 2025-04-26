# Vision AI Studio 🚀🧠✨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Choose appropriate license -->
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/Framework-Flask%20%26%20SocketIO-red.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-MongoDB-green.svg)](https://www.mongodb.com/)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-Gemini%20API-purple.svg)](https://ai.google.dev/)

Vision AI Studio is an innovative, full-stack platform built around **autonomous AI agents** 🤖. Powered by the **Google Gemini API**, it redefines human-AI collaboration by enabling agents to understand complex goals, plan multi-step workflows, interact multimodally (🗣️ text, 🎙️ voice, planned 🖼️ image), and automate tasks end-to-end with minimal human intervention.

**[Link to Live Demo (if applicable)]()** | **[Link to Full Documentation (if applicable)]()**

---

## ✨ Abstract

Vision AI Studio tackles workflow fragmentation and high cognitive load by providing an intelligent ecosystem where specialized AI agents collaborate. Leveraging Gemini for reasoning and orchestration, the platform handles tasks ranging from complex **data analysis & visualization** 📊 and **PDF querying** 📄 to **news aggregation/summarization** 📰, **multilingual voice assistance** 🌐, and **email automation** 📧. Its core innovation lies in **agentic autonomy**, allowing the system to self-configure workflows and adapt, moving beyond simple automation towards intelligent operational management.

---

## 🎯 Core Capabilities

*   🤖 **Autonomous Agent Operation:** Agents plan, decide, use tools (APIs, DB), and execute complex tasks based on high-level goals.
*   🗣️🎙️🖼️ **Multimodal Interaction:** Engage naturally via text, voice (STT/TTS), or planned image inputs for seamless collaboration.
*   ⚙️ **Self-Configuring Workflows:** Gemini API dynamically generates and manages task pipelines based on context and objectives.
*   🧠 **Advanced Context & Memory:** Maintains conversational flow and utilizes persistent storage (MongoDB) for longer-term context awareness.
*   📊 **Integrated Data Analysis:** Upload (CSV/XLSX), clean, analyze (Pandas), visualize (Plotly), and get AI-driven insights for your data.
*   📄 **Intelligent PDF Interaction:** Extract text from PDFs and engage in contextual Q&A about their content.
*   📰 **Real-time News Agent:** Fetch, display, summarize, and read aloud news articles from configured sources.
*   🌐 **Multilingual Voice Agent:** Converse with the AI in multiple languages using integrated STT and TTS.
*   📧 **Email Automation:** (Implemented) Autonomously categorize, prioritize, and draft email responses based on rules and context.
*   💡 **Image Generation:** (Conceptual/Basic) Generate images from text prompts via integrated APIs.
*   ♾️ **Extensible & Scalable:** Modular architecture built with Flask, SocketIO, and MongoDB, ready for containerization and cloud deployment.

---

## 🛠️ Technology Stack

*   **AI Engine:** Google Gemini API
*   **Backend:** Python, Flask, Flask-SocketIO, Eventlet/Gevent
*   **Database:** MongoDB (with Pymongo)
*   **Frontend:** HTML5, CSS3, JavaScript (Vanilla), Bootstrap 5
*   **Real-time:** WebSockets (via Socket.IO)
*   **Data Handling:** Pandas, PyMuPDF (Fitz)
*   **Visualization:** Plotly (Python backend & Plotly.js frontend)
*   **Data Tables:** Tabulator.js
*   **External APIs:** World News API, Google APIs (OAuth, potentially Gmail), etc.

---

## 🚀 Getting Started

Follow these steps to set up and run Vision AI Studio locally.

**1. Prerequisites:**

*   Python 3.9+
*   Git
*   MongoDB Instance (Local, Atlas, or Docker) - Ensure it's running.
*   API Keys (Gemini mandatory; others as needed) - See Configuration.

**2. Clone Repository:**

```bash
git clone <your-repository-url> vision-ai-studio
cd vision-ai-studio
```

**3. Setup Virtual Environment:**

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate.bat # Windows Cmd
# .venv\Scripts\Activate.ps1 # Windows PowerShell
```

**4. Install Dependencies:**

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e . # Editable install for the 'src' package
```

**5. Configure Environment:**

*   Copy the `.env.example` file (if provided) or create a new file named `.env` in the project root (`vision-ai-studio/.env`).
*   Edit the `.env` file and add your specific credentials and settings:
    ```dotenv
    # --- MUST CONFIGURE ---
    FLASK_SECRET_KEY='YOUR_STRONG_RANDOM_SECRET'
    MONGODB_URI="YOUR_MONGODB_CONNECTION_STRING"
    MONGODB_DB_NAME="YOUR_DATABASE_NAME"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

    # --- OPTIONAL / AS NEEDED ---
    FLASK_DEBUG=True
    WORLD_NEWS_API_KEY="YOUR_WORLD_NEWS_API_KEY"
    # ... Google OAuth Credentials if using Google Login ...
    GOOGLE_OAUTH_CLIENT_ID="..."
    GOOGLE_OAUTH_CLIENT_SECRET="..."
    # ... Other settings from documentation Appendix ...
    ```
    *(Refer to the full documentation (Section 14.1) for all variables)*

**6. Run the Application:**

```bash
python run.py
```

**7. Access:** Open your browser and navigate to `http://127.0.0.1:5000` (or the host/port configured).

---

## 📖 Usage

1.  **Register / Login:** Create an account or log in using password or Google OAuth (if enabled).
2.  **Dashboard:** Access different agents and services from the main dashboard.
3.  **Interact:** Use the specific interfaces for each agent (uploading files, typing queries, speaking commands, chatting).
4.  **(Refer to Full Documentation - Section 9 - for detailed agent usage guides)**

---

## 🗺️ Roadmap & Future Work

*   **New Agents:** Calendar Scheduling, CRM Integration, Web Research, Advanced Image Editing.
*   **Scalability:** Implementing robust asynchronous task queues (Celery/RQ).
*   **Memory:** Integrating Vector Databases for enhanced long-term context and semantic retrieval.
*   **Learning:** Incorporating user feedback loops for agent self-improvement.
*   **Deeper Integrations:** More sophisticated inter-agent communication and tool usage.

---

## 🤝 Contribution

Contributions are welcome! Please refer to the `CONTRIBUTING.md` file (if available) or the Development & Contribution section in the full documentation for guidelines on reporting issues, submitting pull requests, code style, and testing.

1.  Check [Issues](link-to-issues-page) for existing tasks or bugs.
2.  Fork the repository.
3.  Create a feature branch (`git checkout -b feature/YourFeature`).
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/YourFeature`).
6.  Open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details (assuming MIT license).

---

*(Optional: Add badges for build status, coverage, etc. if CI/CD is set up)*