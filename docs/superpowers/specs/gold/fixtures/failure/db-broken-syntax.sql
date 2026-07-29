-- 실패 재현 픽스처: 파싱 실패 (구문이 깨진 CREATE TABLE)
-- 기대: 추출 0건 + 실패 1건 보고. 조용히 0건을 반환하면 실패.
CREATE TABLE TB_BROKEN (
  ID   CHAR(10) PRIMARY KEY,
  NAME VARCHAR(100)
  -- 닫는 괄호가 없다
;
