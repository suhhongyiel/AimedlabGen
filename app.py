# app.py

import streamlit as st
import torch
import torchvision.transforms as transforms
from PIL import Image
import os
import numpy as np
import sqlite3
from sqlite3 import Error
import pandas as pd
from math import log10, sqrt

# 데이터베이스 초기화 함수
def init_db(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                psnr REAL NOT NULL
            )
        ''')
        conn.commit()
    except Error as e:
        st.error(f"데이터베이스 오류: {e}")
    finally:
        if conn:
            conn.close()

# 점수 저장 함수
def save_score(db_file, username, psnr):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scores (username, psnr) VALUES (?, ?)
        ''', (username, psnr))
        conn.commit()
    except Error as e:
        st.error(f"데이터베이스 오류: {e}")
    finally:
        if conn:
            conn.close()

# 리더보드 가져오기 함수
def get_leaderboard(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        df = pd.read_sql_query("SELECT username, psnr FROM scores ORDER BY psnr DESC", conn)
        return df
    except Error as e:
        st.error(f"데이터베이스 오류: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

# PSNR 계산 함수
def calculate_psnr(original, generated):
    mse = np.mean((np.array(original) - np.array(generated)) ** 2)
    if mse == 0:
        return float('inf')
    max_pixel = 255.0
    psnr = 20 * log10(max_pixel / sqrt(mse))
    return psnr

# 메인 함수
def main():
    st.title("모델 평가 및 리더보드")

    # 데이터베이스 초기화
    db_file = 'scores.db'
    init_db(db_file)

    # 사용자 이름 입력
    username = st.text_input("사용자 이름을 입력하세요")

    # 모델 업로드
    uploaded_model = st.file_uploader("생성 모델을 업로드하세요 (PyTorch .pt 파일)", type=["pt"])

    if uploaded_model is not None and username:
        try:
            # 모델 로드
            model = torch.load(uploaded_model, map_location=torch.device('cpu'))
            model.eval()

            # 이미지 변환 정의
            transform = transforms.Compose([
                transforms.Resize((256, 256)),
                transforms.ToTensor()
            ])

            # 숨겨진 이미지 로드
            image_folder = '.hidden_images'  # 숨겨진 이미지 폴더 이름
            image_files = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]

            psnr_values = []

            for img_file in image_files:
                img_path = os.path.join(image_folder, img_file)
                original_image = Image.open(img_path).convert('RGB')
                input_tensor = transform(original_image).unsqueeze(0)

                # 모델 추론
                with torch.no_grad():
                    generated_tensor = model(input_tensor)

                # 텐서를 이미지로 변환
                generated_image = transforms.ToPILImage()(generated_tensor.squeeze(0))

                # PSNR 계산
                psnr = calculate_psnr(original_image, generated_image)
                psnr_values.append(psnr)

            # 평균 PSNR 계산
            average_psnr = sum(psnr_values) / len(psnr_values)

            # 점수 저장
            save_score(db_file, username, average_psnr)

            st.success(f"평가 완료! PSNR: {average_psnr:.2f}")

        except Exception as e:
            st.error(f"오류가 발생하여 점수가 저장되지 않았습니다: {e}")

    # 리더보드 표시
    st.subheader("리더보드")
    leaderboard_df = get_leaderboard(db_file)
    st.table(leaderboard_df)

if __name__ == "__main__":
    main()
