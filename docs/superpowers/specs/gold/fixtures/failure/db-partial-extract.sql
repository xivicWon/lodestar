-- 실패 재현 픽스처: 부분 추출
-- 성공 2 · 실패 1 · 미지원 1 이 한 입력에 섞여 있다.
-- 기대: TB_OK_ONE·TB_OK_TWO 2건 추출 + 실패 1건 + 제외 1건을 모두 보고.
-- "2건 추출했다"만 말하고 나머지 2건을 말하지 않으면 부분 성공을 완전 성공으로 위장한 것이다.

CREATE TABLE TB_OK_ONE (
  ONE_ID   CHAR(10) PRIMARY KEY,
  ONE_NM   VARCHAR(50)
);

CREATE TABLE TB_BAD_MIDDLE (
  BAD_ID   CHAR(10) PRIMARY KEY
  BAD_NM   VARCHAR(50)    -- 쉼표 누락 → 파싱 실패
);

CREATE INDEX IX_OK_ONE_NM ON TB_OK_ONE (ONE_NM);

CREATE TABLE TB_OK_TWO (
  TWO_ID   CHAR(10),
  TWO_SEQ  INTEGER,
  TWO_AMT  NUMERIC(18,2),
  PRIMARY KEY (TWO_ID, TWO_SEQ)
);
