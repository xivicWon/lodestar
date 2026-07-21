package com.x
class Svc {
    fun handle() { save(1) }   // 자기 자신 save 존재 → 같은 타입 유일 → EXTRACTED
    fun save(n: Int) {}
}
class Store {
    fun save(n: Int) {}
}
class Client {
    fun use() { save(1) }      // Client엔 save 없음; Repo.save+Store.save+Svc.save 3후보, 같은타입 0 → AMBIGUOUS
}
