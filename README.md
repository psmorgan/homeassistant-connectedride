# BMW Connected Ride for Home Assistant

[![HACS][hacs-badge]][hacs-url]
[![License: MIT][license-badge]][license-url]

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://hacs.xyz
[license-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[license-url]: LICENSE

A Home Assistant custom integration for BMW motorcycles using the BMW Connected Ride API. Exposes 37 sensors per motorcycle including telemetry, ride statistics, GPS tracking, and motorcycle images.

![BMW Connected Ride screenshot](images/screenshot.png)

## Features

### Core Telemetry

- Fuel level and remaining range
- Energy level and electric range (electric/hybrid models, disabled by default)
- Front and rear tire pressures
- Odometer (mileage) with ABS type info
- Trip distance
- Next service date and distance to service
- GPS device tracker
- Motorcycle images (side views, rider views)

### Bike Field Sensors

- Last activated timestamp
- Total connected distance and duration
- Charging mode and charging time estimation (electric models)

### Last Ride Statistics — 14 sensors from recorded tracks

- Distance, duration, average and max speed
- Min and max ambient temperature
- Elevation gain and loss
- Max lean angles (left and right)
- Max acceleration and braking
- Max RPM

### Aggregate Ride Statistics — 7 sensors from all recorded tracks

- Total ride count
- Total and average distance
- Total and average duration
- Longest ride distance
- Highest lean angle

## Installation

1. Install [HACS](https://hacs.xyz) if not already installed
2. In HACS, go to Integrations and click the three-dot menu
3. Select "Custom repositories"
4. Add the repository URL and select "Integration" as the category
5. Search for "BMW Connected Ride" and install
6. Restart Home Assistant
7. Go to Settings > Devices & Services > Add Integration > search "BMW Connected Ride"

## Disclaimer

BMW, Connected Ride, and Motorrad are trademarks of BMW AG. This project is not endorsed by, affiliated with, or sponsored by BMW AG. This integration uses unofficial BMW APIs that may change or be discontinued without notice.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
