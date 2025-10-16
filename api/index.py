import os
import json
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from typing import Optional

# Cấu hình Discord Interaction Types
PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3
AUTOCOMPLETE = 4
MODAL_SUBMIT = 5

# Cấu hình tính toán vé
BLACK_TICKET_PER_MONTH = 81
RELIC_TICKET_PER_MONTH = 18

# Lấy PUBLIC_KEY từ biến môi trường Vercel (BẮT BUỘC)
PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
if not PUBLIC_KEY:
    raise RuntimeError("DISCORD_PUBLIC_KEY environment variable is not set.")

try:
    # Khởi tạo VerifyKey để xác minh chữ ký của Discord
    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
except Exception as e:
    print(f"Error initializing VerifyKey: {e}")
    raise

# Khởi tạo ứng dụng FastAPI
app = FastAPI()

def verify_signature(request: Request, body: bytes):
    """Xác minh chữ ký để đảm bảo request đến từ Discord."""
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")

    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature or timestamp.")

    message = timestamp.encode() + body

    try:
        verify_key.verify(message, bytes.fromhex(signature))
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="Invalid signature.")


def handle_calc_command(data: dict):
    """
    Xử lý lệnh /calc.
    Lệnh này nhận 3 options: ticket_type, current_tickets, months.
    """
    options = {opt['name']: opt['value'] for opt in data['options']}
    
    ticket_type = options.get('type')
    current_tickets = options.get('current_tickets')
    months = options.get('months')

    # Logic tính toán (luôn tính từ tháng sau)
    per_month = BLACK_TICKET_PER_MONTH if ticket_type == "đen" else RELIC_TICKET_PER_MONTH
    
    results = []
    # Bắt đầu tính từ tháng 1 (tháng tới)
    for i in range(1, months + 1):
        total = current_tickets + per_month * i
        results.append(f"Tháng {i} (Sau {i} tháng): **{total} vé {ticket_type}**")

    content = (
        f"📅 **Kết quả dự tính vé {ticket_type}**\n"
        f"Số vé hiện tại: {current_tickets} | Tính trong {months} tháng.\n"
        "---"
        "\n" + "\n".join(results)
    )

    # Trả về một phản hồi tạm thời (phản hồi theo lệnh Slash)
    return {
        "type": 4, # CALLBACK_TYPE.CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "content": content,
            "flags": 64 # FLags.EPHEMERAL (chỉ người dùng thấy)
        }
    }


# Endpoint chính mà Discord sẽ gọi
@app.post("/interactions")
async def interactions(request: Request):
    # Lấy body dưới dạng bytes để xác minh chữ ký
    body = await request.body()
    
    # BƯỚC 1: Xác minh chữ ký
    try:
        verify_signature(request, body)
    except HTTPException as e:
        return e.detail

    data = json.loads(body.decode("utf-8"))
    
    # BƯỚC 2: Xử lý PING
    if data["type"] == PING:
        # Phản hồi PONG để Discord biết endpoint đang hoạt động
        return {"type": 1} # CALLBACK_TYPE.PONG
    
    # BƯỚC 3: Xử lý lệnh Slash
    elif data["type"] == APPLICATION_COMMAND:
        command_name = data["data"]["name"]
        
        if command_name == "calc":
            return handle_calc_command(data["data"])
        
    # Nếu không phải là PING hoặc Lệnh, trả về lỗi
    raise HTTPException(status_code=400, detail="Invalid interaction type.")


# Endpoint cho Vercel kiểm tra trạng thái
@app.get("/")
def read_root():
    return {"status": "Bot WebHook is running on Vercel"}

# FastAPi cần uvicorn để chạy, Vercel sẽ tự động cấu hình điều này qua file vercel.json (nếu có)
# Tuy nhiên, chỉ cần FastAPI và requirements.txt là đủ cho Vercel.
