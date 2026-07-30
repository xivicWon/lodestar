package fixture.beta

/**
 * L2 drift 픽스처 revC. revB 대비:
 *  - 재등장: legacyReport() 가 revB 에서 삭제됐다가 같은 이름·같은 소유 타입으로 되돌아왔다.
 *    revA 의 그것과 같은 것으로 볼지(부활) 새 것으로 볼지가 L3 재등장 시나리오의 쟁점이다.
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

    /** revB 에서 사라졌다가 revC 에서 되돌아왔다. 본문은 revA 와 동일. */
    fun legacyReport(): String = "legacy"
}
