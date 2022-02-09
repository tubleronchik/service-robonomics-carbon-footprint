# Robonomics Carbon Footprint Service

Service to offset CO2 footprint by burning tokens in Statemine network. 
1 MWh of non-renewable electricity produces 1 ton of C02. 1 ton of C02 is covered by consuption of 1 token.

## Installing

Clone the repository and edit config file.

```
gir clone https://github.com/tubleronchik/service-robonomics-carbon-footprint.git
cd service-robonomics-carbon-footprint
cp config/config_template.yaml config/config.yaml 
```

## Configuration description

Do not edit `config/config_template.yaml`!

```
robonomics:
  seed: <seed for account in Robonomics Network where Digital Twin will be created>
statemine:
  seed: <seed for admin account with green tokens in Statemine Netowrk>
  endpoint: <statemine endpoint>
  token_id: <id of the token which will be burned>
  ss58_format: <format of address in Polkadot (for Statemine Network is 2)>

service:
  interval: <how often data from devices will be collected>
```
Coefficients for non-renewable energy have been taken from [Eurostat](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=File:Renewable_energy_2020_infographic_18-01-2022.jpg) and stored in `utils/coefficients.py`. 

## Launch

```
docker build --tag service-robonomics-carbon-footprint . 
docker run -t service-robonomics-carbon-footprint    
```

