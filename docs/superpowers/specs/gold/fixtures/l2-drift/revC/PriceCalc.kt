package fixture.gamma

/**
 * revA 의 fixture.alpha.PriceCalc 와 이름만 같은 별개 타입이다(본문·의미 무관).
 * revA.PriceCalc → revC.PriceCalc 를 정체성 링크로 묶으면 고신뢰 오연결이다.
 * revA.PriceCalc 의 후신은 revB/revC 의 fixture.beta.PricingCalculator 다.
 */
class PriceCalc {
    fun formatReceipt(orderNo: String): String = "RECEIPT-$orderNo"
}
