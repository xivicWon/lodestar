package com.x;
import com.x.Repo;
public class Foo extends Base {
    void run() {
        new Repo().save(1);
        System.out.println("hi");   // println 미정의 → external_calls 카운트, 엣지 없음
    }
}
