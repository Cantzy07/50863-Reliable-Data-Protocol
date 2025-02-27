# Python
PYTHON = python3

# Paths to student scripts
SENDER_PATH = "./sender_stop_and_go.py"
RECEIVER_PATH = "./receiver_stop_and_go.py"

# Ports to clear
# These ports are currently hardcoded in the config file. 
# If you modify the ports in config file they should be changed here as well. 
SENDER_PORT = 8001
RECEIVER_PORT = 8002

CONFIG = "../../TestConfig/config1.ini"

# Runs the sender
run-sender:
	-powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort $(SENDER_PORT)).OwningProcess -Force"
	$(PYTHON) $(SENDER_PATH) "$(CONFIG)"

# Runs the receiver
run-receiver:
	-powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort $(RECEIVER_PORT)).OwningProcess -Force"
	$(PYTHON) $(RECEIVER_PATH) "$(CONFIG)"
