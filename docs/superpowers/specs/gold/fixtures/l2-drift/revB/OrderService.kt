package fixture.beta

/**
 * L2 drift 픽스처 revB. revA 대비 네 가지가 동시에 일어났다.
 *  - 이동: fixture.alpha → fixture.beta (같은 타입, 다른 패키지)
 *  - rename: PriceCalc → PricingCalculator (본문 동일)
 *  - 삭제: legacyReport() 제거
 *  - 오버로드: placeOrder(String, String) 추가
 */
class OrderService(private val calc: PricingCalculator) {

    fun placeOrder(orderNo: String): String {
        val amount = calc.calc(orderNo.length)
        return "$orderNo:$amount"
    }

    fun placeOrder(orderNo: String, memo: String): String {
        val amount = calc.calc(orderNo.length)
        return "$orderNo:$amount:$memo"
    }

    fun cancelOrder(orderNo: String): Boolean = orderNo.isNotBlank()
}
