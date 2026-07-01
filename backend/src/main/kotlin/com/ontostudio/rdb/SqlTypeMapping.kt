package com.ontostudio.rdb

private const val XSD = "http://www.w3.org/2001/XMLSchema#"

/** SQL 타입 문자열(길이/정밀도 파라미터 포함 가능)을 XSD 데이터타입 IRI로 매핑. 미지의 타입은 xsd:string. */
fun sqlTypeToXsd(sqlType: String): String {
    val t = sqlType.trim().lowercase().substringBefore('(').trim()
    return when {
        t.contains("char") || t.contains("text") || t.contains("clob") -> XSD + "string"
        t.contains("bool") -> XSD + "boolean"
        t.startsWith("timestamp") || t.startsWith("datetime") -> XSD + "dateTime"
        t == "date" -> XSD + "date"
        t.startsWith("time") -> XSD + "time"
        t.contains("int") || t == "serial" || t == "bigserial" -> XSD + "integer"
        t.contains("numeric") || t.contains("decimal") || t.contains("real") ||
            t.contains("double") || t.contains("float") || t == "money" -> XSD + "decimal"
        else -> XSD + "string"
    }
}
