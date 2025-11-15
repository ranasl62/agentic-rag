# For Ubuntu 22.04 (jammy) or newer:
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) && echo "Distribution: $distribution"

# Add NVIDIA repository with correct distribution
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# If the above fails, try the generic approach:
sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list << 'EOF'
deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/$(. /etc/os-release && echo $ID$VERSION_ID)/$(dpkg --print-architecture) /
EOF

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit