### Disclaimer
This is a personal project I decided to package into an integration and share with anyone who's as meticulous about personal finance and financial stability as I am. That said,
**you alone is responsible for the safety of your money**, including information security of your home server setup, as this integration requires logging in to your T-Bank account via a Selenium client, which means
a bad actor could do something bad if they ever gained access to your Selenium instance.   
It would also be a good idea to go through the code of this integration and ensure I'm not a bad actor, silently sending your T-Bank session IDs somewhere, [client.py](client.py) is a good place to start.

## Installation
I don't want to bother with HACS before it is needed, so you need to mannualy copy all the files of this repo into `<config>/custom_components/tbank/` and restart your HA instance.  
You will also need a Selenium Grid instance, which you can run as an add-on thanks to [David Amor](https://github.com/davida72): https://github.com/davida72/selenium-homeassistant.  
Then add the T-Bank integration and follow the configuration flow.

## How it can be used
This integration creates sensors for all your bank accounts, all your investment accounts (if any), and every security you have in each of your investment accounts, and creates a tree-like structure via the sensors' 
attriburtes, which allows to build, for example, a self-updating Sankey chart with templates. Here's an example:

<img width="100%" alt="image" src="https://github.com/user-attachments/assets/89092cea-374e-45a2-add7-a1b27204bceb" />
