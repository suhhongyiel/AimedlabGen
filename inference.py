# inference.py
import torch

def run_inference(model_path):
    """
    모델을 로드하고 추론을 수행하는 함수.
    """
    # 모델 로드
    model = torch.load(model_path)
    model.eval()
    
    # 예제 데이터 (실제 데이터로 교체 필요)
    dummy_input = torch.randn(1, 3, 224, 224)  # 예: 이미지 입력
    with torch.no_grad():
        output = model(dummy_input)
    
    # 추론 결과를 반환 (필요에 따라 포맷 변경)
    return {"data": output.squeeze().tolist()}
