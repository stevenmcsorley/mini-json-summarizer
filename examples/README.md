# Examples

Real-world examples showcasing Mini JSON Summarizer in action.

## 📊 Live Error Monitoring Dashboard

**[`live-dashboard/`](live-dashboard/)** - Production-ready operational dashboard with SSE streaming

**Features:**
- Real-time error aggregation via Server-Sent Events
- Service health heatmap (red/yellow/green)
- Live error rate charts with Chart.js
- Profile-powered log analysis (uses actual Mini JSON Summarizer)

**Quick Start:**
```bash
cd live-dashboard
docker-compose up
open http://localhost:3000
```

**What you'll see:**
- 3 microservices generating realistic errors
- Live dashboard updating in real-time
- Top-K error codes, service health, temporal spikes
- All powered by the `logs` profile

**Perfect for:**
- Showcasing SSE streaming capabilities
- Demonstrating profiles system in action
- Learning operational monitoring patterns
- Demo/POC presentations

---

## 🎯 More Examples Coming Soon

- **CI/CD Integration** - GitHub Actions workflow with error threshold gates
- **Slack Bot** - Real-time incident summaries to Slack channels
- **Grafana Plugin** - Custom panel for JSON log visualization
- **AWS Lambda** - Serverless log processing at scale

---

## 🤝 Contributing Examples

Have a cool use case? Submit a PR with:

1. Self-contained directory in `examples/`
2. `README.md` with quick start instructions
3. `docker-compose.yml` for easy setup
4. Uses actual Mini JSON Summarizer (not mocked)

---

## 📄 License

MIT © 2025 Steven McSorley
