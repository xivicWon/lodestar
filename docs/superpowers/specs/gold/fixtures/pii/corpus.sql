-- PII·시크릿 마스킹 테스트 코퍼스 (#88 L0 보안 게이트용) — 전부 합성 데이터다.
-- 실존 인물·계정·자격증명이 아니며, 여기 값을 실제 시스템에 쓰면 안 된다.
-- 각 줄의 정답(마스킹 대상 여부)은 ../../pii.json 에 좌표로 고정돼 있다.

CREATE TABLE TB_PII_MEMBER (
  MBR_NO   CHAR(10) PRIMARY KEY,
  MBR_NM   VARCHAR(50),
  RRN      CHAR(14),
  EMAIL    VARCHAR(120),
  TEL_NO   VARCHAR(20),
  CARD_NO  VARCHAR(19),
  ACCT_NO  VARCHAR(30),
  ADDR     VARCHAR(200)
);

-- 양성: 이 INSERT 의 값들은 전부 마스킹 대상이다.
INSERT INTO TB_PII_MEMBER VALUES
  ('M000000001', '홍길동', '900101-1234567', 'hong@example.com', '010-1234-5678', '4111-1111-1111-1111', '110-234-567890', '서울시 강남구 테헤란로 152 5층');
INSERT INTO TB_PII_MEMBER VALUES
  ('M000000002', '김철수', '851212-2345678', 'kim.cs@example.co.kr', '+82-10-9876-5432', '5555555555554444', '1002-345-678901', '부산시 해운대구 센텀중앙로 90');

-- 음성(오탐 유발): 아래 값들은 개인정보도 자격증명도 아니다. 마스킹하면 오탐이다.
INSERT INTO TB_ITEM_MST (ITEM_CD, ITEM_NM, STD_PRC) VALUES
  ('ITM000000001', '스테인리스 볼트 M8', 150.00);
INSERT INTO TB_ORD_HD (ORD_NO, ORD_DT, TOT_AMT) VALUES
  ('ORD202401000001', '2024-01-05 11:20:00', 1650000.00);
INSERT INTO TB_ACCT_CD (ACCT_CD, ACCT_NM) VALUES
  ('410100', '제품매출');
