package fixture.failure

// 실패 재현 픽스처: 파싱 실패 (중괄호 불균형)
// 기대: 이 파일에서 추출 0건 + 파싱 실패 1건 보고. 부분 트리로 절반만 건져 조용히 넘어가면 실패.

class BrokenSyntax {

    fun half(): String {
        val x = "unterminated
        return x
    // 닫는 중괄호가 둘 모자란다
