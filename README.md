# ☁️ ARC - Amazon Resources Controller

**ARC-cli** is a powerful command-line tool designed to simplify the process of managing Amazon Web Services (AWS) resources. 
This project aims to provide an intuitive interface for developers to interact with the cloud,
helping them easily create, delete, and edit resources on AWS without the complexity of the web console or the need to remember complex commands.

---
## 🚀 Features

### 🖥️ Compute (EC2)
* **Interactive Launch:** Step-by-step wizard to launch instances (Ubuntu / Amazon Linux 2023).
* **Key Management:** Automatically detects local keys or generates new RSA key pairs on the fly.
* **Safety Quotas:** Prevents accidental costs by limiting users to **2 active instances**.
* **Lifecycle Management:** Start, Stop, and Terminate instances.
* **Bulk Actions:** Terminate all managed instances with `delete ec2 --all`.

### 📦 Storage (S3)
* **Smart Creation:** Checks for global name availability and suggests alternatives if taken.
* **Recursive Delete:** Force delete non-empty buckets or wipe all ARC buckets with `delete s3 --all`.
* **Upload:** Easily upload files to your buckets.

### 🌐 Networking (Route53)
* **DNS Management:** Create and delete Public Hosted Zones.
* **Record Sets:** Add A-Records (IPs) to your domains easily.
* **Clean Up:** Deeply deletes zones (removes records first) to ensure successful deletion.
## 🛠️ Installation

### Prerequisites
* Python 3.8+
* AWS Credentials (Access Key & Secret Key) configured via `aws configure`.

### Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/alondudi/ARC-cli.git](https://github.com/alondudi/ARC-cli.git)
    cd ARC-cli
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv

    # Windows:
    venv\Scripts\activate

    # Mac/Linux:
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install ARC as a command (Editable Mode):**
    ```bash
    pip install -e .
    ```

5.  **AWS Credentials Setup:**
    ```bash
    arc setup
    ```


## Usage Guide
To use ARC-cli, you can run the following command:
```bash
arc --help
```
This will display the available commands and options you can use with ARC-cli.

## 📂 Project Structure

```text
ARC-cli/
│
├── arc_cli.py             # Main CLI Entry Point
├── requirements.txt       # Dependencies (boto3, click, rich)
├── README.md              # Documentation
│
├── services/              # AWS Boto3 Logic
│   ├── aws_client.py      # Main Connection Handler
│   ├── ec2.py             # Compute Logic
│   ├── s3.py              # Storage Logic
│   └── route53.py         # Networking Logic
│
└── keys/                  # Generated SSH Keys (Auto-created)
```

Author
Alon
