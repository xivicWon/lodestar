-- 실패 재현 픽스처: 미지원 문법 (트리거 · PL/pgSQL 본문)
-- 기대: 추출 0건 + "미지원 구문" 사유와 함께 제외 보고.
-- 덧붙여: 본문 안의 ';' 때문에 ';' 단순 분할 방식은 이 한 문장을 여러 조각으로 쪼갠다.
-- 그 조각들이 각각 파싱 실패로 세어지면 실패 건수가 부풀고, 조용히 버려지면 은폐다.
-- 둘 중 어느 쪽인지가 이 픽스처의 관측 지점이다.
CREATE TRIGGER TRG_ORD_AUDIT
  AFTER INSERT ON TB_ORD_HD
  FOR EACH ROW
EXECUTE FUNCTION FN_ORD_AUDIT();

CREATE OR REPLACE FUNCTION FN_ORD_AUDIT() RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO TB_LOG_HIST (TBL_NM, ACT_GBN, ACT_DT)
  VALUES ('TB_ORD_HD', 'I', NOW());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
