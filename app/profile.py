"""Local candidate profile template.

Keep real resume paths and personal application details in your private working copy.
This public repository intentionally ships with example values only.
"""

CANDIDATE_PROFILE = {
    "name": "Your Name",
    "location": "City, ST",
    "verified_technical_experience_years": None,
    "certifications": [],
    "education": [
        "Your completed degree",
        "Your in-progress education",
    ],
    "resume_files": {
        "cybersecurity": {
            "label": "Cybersecurity / SOC",
            "file_path": r"C:\path\to\cybersecurity_resume.docx",
        },
        "cloud_devops": {
            "label": "Cloud / DevOps / Infrastructure",
            "file_path": r"C:\path\to\cloud_devops_resume.docx",
        },
        "it_systems_network": {
            "label": "IT Systems / Network / Security",
            "file_path": r"C:\path\to\it_resume.docx",
        },
    },
}
