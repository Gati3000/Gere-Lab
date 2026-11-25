# Gere-Lab
Tools for Gere for operating his comapany

<!-- GERE-INSTALL -->
## Installation

Create a Debian/Ubuntu container (or VM), open its terminal as root, then copy and paste the whole block below. It installs the basics, downloads Gere-Lab and starts the Launcher, which asks a few questions and sets everything up.

```bash
cd ~ && apt-get update && apt-get install -y git python3 \
  && git clone -b Main https://github.com/Gati3000/Gere-Lab.git \
  && python3 Gere-Lab/App/Launcher/Launcher.py
```

Want the testing version? Use the Beta branch instead:

```bash
cd ~ && apt-get update && apt-get install -y git python3 \
  && git clone -b Beta https://github.com/Gati3000/Gere-Lab.git \
  && python3 Gere-Lab/App/Launcher/Launcher.py
```

When the Launcher finishes, start the program:

```bash
Lab start
```

## Commands

| Command | What it does |
|---|---|
| `Lab start` (or `Lab -up`) | start Gere-Lab |
| `Lab stop` (or `Lab -s`) | stop Gere-Lab |
| `Lab restart` | stop and start again |
| `Lab update` (or `Lab update -m`) | check the Main branch (stable) and update, also switches back from Beta |
| `Lab update -b` | the same for the Beta branch (testing) |
| `Lab branch` | show the current branch and version |
| `Lab setup` | run the first-time setup again |
| `Lab remove` (or `Lab -rm`) | remove Gere-Lab (asks for the root password) |
| `Lab drive` | update Gere-Drive (if installed) |
| `Lab help` | show help |

To run the Launcher again by hand:

```bash
python3 ~/Gere-Lab/App/Launcher/Launcher.py
```
