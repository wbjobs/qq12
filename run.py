import asyncio
import uvicorn
from udp_service import UDPService
from main import app, set_udp_service


async def main():
    udp_service = UDPService()
    set_udp_service(udp_service)

    await udp_service.start()

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        await udp_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
