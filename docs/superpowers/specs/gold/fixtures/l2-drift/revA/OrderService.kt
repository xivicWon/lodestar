package fixture.alpha

/** L2 drift 픽스처 revA. revB 에서 패키지 이동·rename·삭제·오버로드가 동시에 일어난다. */
class OrderService(private val calc: PriceCalc) {

    fun placeOrder(orderNo: String): String {
        val amount = calc.calc(orderNo.length)
        return "$orderNo:$amount"
    }

    fun cancelOrder(orderNo: String): Boolean = orderNo.isNotBlank()

    /** revB 에서 삭제된다. */
    fun legacyReport(): String = "legacy"
}
