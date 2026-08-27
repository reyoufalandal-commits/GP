# Compliance and retention (pointers)

This project does not provide legal advice. Before deploying flow capture and scoring in production:

- Define **data retention** for NetFlow-like records and ML outputs.
- Align **monitoring** with organizational policy and applicable regulations.
- Restrict access to **training and alert** stores; use [`hawk_eye.redact`](../src/hawk_eye/redact.py) where exporting samples.
