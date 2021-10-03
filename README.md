# OctoPrint-PSUControl-MQTT
MQTT subplugin for PSU Control

Lets you control any MQTT controlled switch with PSU Control.

- choose as subplugin for switching/sensing in PSU Control settings
- set MQTT topics and messages to the ones your switch/device expects in this plugins' settings.


# What you need:
 - [MQTT](https://github.com/OctoPrint/OctoPrint-MQTT) plugin for OctoPrint
 - [PSU Control](https://github.com/kantlivelong/OctoPrint-PSUControl) plugin for OctoPrint

# How to configure:
This depends on your device. 
Some expect a simple raw text like 'ON' while others expect json type messages like '{"POWER":"ON"}'.
Some have dedicated topics to which they write only the current state, others write the status json style into a topic after you ask them to (query).
Some do both (Tasmota for example).

To find out which settings you need, check the documentation of your device. 
