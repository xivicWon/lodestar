package fixture.failure

// 실패 재현 픽스처: 부분 추출
// 앞의 GoodOne 은 완전하고, 뒤의 TailBroken 은 깨져 있다.
// 기대: GoodOne(타입 1 · 메서드 1)을 추출하되 TailBroken 구간의 파싱 실패를 함께 보고한다.
// 앞부분만 보고 "파일 파싱 성공"으로 표시하면 부분 추출을 완전 추출로 위장한 것이다.

class GoodOne {
    fun ok(): Int = 1
}

class TailBroken {
    fun bad(): Int = (1 +
}
