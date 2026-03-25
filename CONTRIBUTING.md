# Contributing to gps-mouse

Thank you for your interest in contributing! Here's how to get started.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/gps-mouse.git
   cd gps-mouse
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b feature/my-feature
   ```
4. **Install in development mode**:
   ```bash
   pip install -e ".[dev]"
   ```

## Making Changes

- Keep changes focused — one feature or fix per pull request
- Follow the existing code style (PEP 8)
- Add or update examples in `examples/` if relevant
- Make sure existing examples still work

## Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feature/my-feature
   ```
2. Open a **Pull Request** on GitHub against the `main` branch
3. Fill in the PR description — what changed and why
4. Wait for a review

## Reporting Issues

- Use [GitHub Issues](../../issues) to report bugs or request features
- Include your OS, Python version, GPS device model, and a minimal reproduction case

## Ideas for Contributions

- Support for additional NMEA sentence types (GSV, GLL, ZDA)
- Windows / macOS serial port detection
- gpsd integration
- PyPI packaging / CI workflow
- Unit tests with mock serial data

## Code of Conduct

Be respectful. Constructive criticism is welcome; personal attacks are not.
