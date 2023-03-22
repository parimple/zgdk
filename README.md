[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# zgdk

This is a Discord bot that does manage discord server channels, gives moderators the tools to manage the server and introduces currency, a ranking system and many other features.
gi

## Prerequisites

- Docker
- Python 3.10 or higher
- Discord account and API token

## Installation

1. Clone the repository:

`git clone https://gitlab.com/patrykpyzel/zgdk.git`

2. Create a `.env` file in the root directory of the project and set the following environment variable:

`DISCORD_TOKEN=<your Discord API token>`

3. Build the Docker image:

`docker build -t zgdk .`

4. Run the Docker container:

`docker run -d --name zgdk zgdk`

## Usage

To use the bot, invite it to a Discord server and use the following commands:

- `!help`: Display a list of available commands.
- `!ping`: Display bot latency.

## Contributing

We welcome contributions to this project. If you are interested in contributing, please follow these guidelines:

- Fork the repository and make your changes in a feature branch.
- Run the tests to ensure that they pass.
- Submit a pull request.

## License

This project is licensed under the MIT License.
