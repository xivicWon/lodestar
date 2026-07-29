package fixture.failure

/*
 * 실패 재현 픽스처: 미지원 언어.
 * E17 수집기는 Java·Kotlin 만 지원한다. 기대: 추출 0건 + "미지원 언어" 사유로 제외 보고.
 * 확장자만 보고 조용히 건너뛰면 은폐다 — 제외 목록에 사유와 함께 나타나야 한다.
 */
object UnsupportedLang {
  def calc(units: Int): Int = units * 100

  case class Receipt(orderNo: String, amount: Int)
}
