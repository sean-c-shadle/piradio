#!/bin/bash

# Bluetooth speakers MAC address needs to be entered here
MAC="XX:XX:XX:XX:XX:XX"

# Give Bluetooth time to initialize  
sleep 10

# Ensure Bluetooth is powered  
bluetoothctl power on

# Retry connection for up to 60 seconds  
for i in {1..12}; do
echo "Bluetooth connect attempt $i..."  

if bluetoothctl connect "$MAC"; then
echo "Bluetooth speakers connected"  
exit 0
fi

sleep 5
done

echo "Failed to connect to Bluetooth speakers"  
exit 1
