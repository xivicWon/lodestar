package com.ontostudio.rdb

import com.ontostudio.provenance.Provenance
import com.ontostudio.provenance.ProvenanceVocab
import com.ontostudio.provenance.RelationKind
import org.semanticweb.owlapi.apibinding.OWLManager
import org.semanticweb.owlapi.model.IRI
import org.semanticweb.owlapi.model.OWLOntology
import org.springframework.stereotype.Component

/** SchemaModel → OWLOntology (TBox only). 무상태: 매 호출마다 새 manager/ontology 생성. */
@Component
class SchemaToOwlMapper {

    /** IRI-안전 슬러그: 공백→_, 문자/숫자/_ 이외 제거. 결정론적(카운터 없음). */
    internal fun slug(name: String): String =
        name.trim().replace(Regex("\\s+"), "_").replace(Regex("[^\\p{L}\\p{N}_]"), "").ifBlank { "x" }

    /**
     * 소속(schema)을 IRI 앞에 붙이는 경로 조각 — `sales/` (#126). 소속을 모르면 빈 문자열이므로
     * 비한정 DDL 로 만든 IRI 는 이 변경 전과 같다.
     *
     * 구분자로 `/` 를 쓰는 이유: [slug] 가 문자·숫자·`_` 만 남기므로 `/` 는 조각 **안에** 나타날 수
     * 없다 — 소속과 이름의 경계가 밀리지 않는다. `.` 을 쓰면 데이터 프로퍼티의 `<테이블>.<컬럼>` 과
     * 겹쳐, 스키마 `a` 의 테이블 `b` 와 테이블 `a` 의 컬럼 `b` 가 같은 IRI 가 된다.
     *
     * 소속이 있으면 **항상** 붙인다. "동명 테이블이 있을 때만" 으로 하면 다른 스키마에 동명
     * 테이블이 하나 생기는 것만으로 기존 테이블의 IRI 가 전부 바뀌어, 재임포트마다 확정(세이브포인트)
     * 매칭이 무너진다(E9).
     */
    private fun qualifier(schema: String?): String = if (schema == null) "" else slug(schema) + "/"

    /**
     * **클래스 IRI 를 만드는 단 하나의 자리.** 소속 표기가 여러 곳에 흩어지면 규약을 바꿀 때 한
     * 곳이 남아, 같은 테이블이 경로에 따라 다른 IRI 를 갖게 된다. 프로퍼티 IRI 도 이 값 위에 쌓는다.
     */
    internal fun classIri(base: String, schema: String?, name: String): IRI =
        IRI.create(base + qualifier(schema) + slug(name))

    internal fun classIri(base: String, table: TableInfo): IRI = classIri(base, table.schema, table.name)

    private fun dataPropIri(base: String, table: TableInfo, column: String): IRI =
        IRI.create(classIri(base, table).toString() + "." + slug(column))

    private fun fkPropIri(base: String, table: TableInfo, fkColumns: List<String>): IRI =
        IRI.create(classIri(base, table).toString() + "_" +
            fkColumns.joinToString("_") { slug(it) } + "_ref")

    /**
     * FK 대상의 클래스 IRI. 스냅샷 안에서 대상 테이블을 찾으면 그 테이블의 IRI 이고, 못 찾으면
     * **FK 가 적어 준 소속을 그대로 살려** IRI 를 만든다(수집 범위 밖의 테이블을 가리키는 FK 는
     * 실제로 있다). 여기서 소속을 버리면 `sales.orders` 와 `archive.orders` 를 가리키는 두 FK 가
     * 같은 클래스로 수렴해, 이 이슈가 없앤 충돌이 '해석 실패' 분기에 그대로 남는다.
     *
     * 해석 우선순위는 SQL 의 이름 해석과 같은 방향이다:
     * 1. 원본이 대상 소속을 적었으면 **그 소속 안에서만** 찾는다. 없으면 거기서 끝이다 —
     *    이름이 같다는 이유로 소속이 다른 테이블에 묶으면 원본에 없는 관계를 `EXTRACTED` ·
     *    confidence 1.0 으로 산출하게 된다.
     * 2. 적지 않았으면 참조하는 쪽의 스키마 안을 먼저 본다.
     * 3. 그래도 없으면 이름이 유일할 때만 그 테이블로 간다 — 후보가 여럿인데 아무거나 고르면
     *    역시 잘못된 관계가 사실이 된다.
     *
     * **남는 한계(기록):** 소속을 적지 않은 참조의 대상이 스냅샷에 없으면, 서로 다른 스키마에서
     * 같은 이름을 가리키는 두 FK 가 한 클래스로 수렴한다. 그때 참조하는 쪽 스키마로 한정하는 것은
     * **모르는 소속을 지어내는 것**이라(실제 대상은 search_path 상의 공용 스키마일 수 있다) 하지
     * 않는다. JDBC 경로는 `PKTABLE_SCHEM` 을 항상 주므로 이 자리는 DDL 텍스트에만 해당한다.
     * 또 해석되지 않은 대상 클래스는 range 공리로만 시그니처에 들어가 선언·라벨이 없다 — #126
     * 이전부터의 성질이고, 이 이슈에서 바꾸지 않았다.
     */
    private fun refTarget(base: String, from: TableInfo, fk: ForeignKeyInfo,
                          byQualified: Map<Pair<String?, String>, TableInfo>,
                          byName: Map<String, List<TableInfo>>): Pair<IRI, String> {
        val resolved = if (fk.refSchema != null) byQualified[fk.refSchema to fk.refTable]
        else byQualified[from.schema to fk.refTable] ?: byName[fk.refTable]?.singleOrNull()

        if (resolved != null) return classIri(base, resolved) to resolved.qualifiedName
        return classIri(base, fk.refSchema, fk.refTable) to
            (fk.refSchema?.let { "$it.${fk.refTable}" } ?: fk.refTable)
    }

    fun build(schema: SchemaModel, baseIri: String): OWLOntology {
        val mgr = OWLManager.createOWLOntologyManager()
        val df = mgr.owlDataFactory
        val ont = mgr.createOntology()

        // FK 대상 해석용 색인. 이름만으로 찾으면 동명 테이블 중 아무 쪽이나 걸린다(#126).
        val byQualified = schema.tables.associateBy { it.schema to it.name }
        val byName = schema.tables.groupBy { it.name }

        for (table in schema.tables) {
            val cls = df.getOWLClass(classIri(baseIri, table))
            mgr.addAxiom(ont, df.getOWLDeclarationAxiom(cls))
            // 라벨은 **원본 테이블 이름 그대로** 둔다. 여기에 소속을 섞으면 라벨이 더 이상 "수집기가
            // 본 이름" 이 아니게 되고, 라벨을 이름으로 쓰는 경로(UI 표시·AI 그라운딩 앵커)가 함께
            // 흔들린다. 동명 테이블을 가르는 일은 신원(IRI)의 몫이다 — 소속은 주석으로 드러낸다.
            mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                cls.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(table.name))))
            if (table.schema != null) {
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    cls.iri, df.getOWLAnnotation(df.rdfsComment,
                        df.getOWLLiteral("schema: ${table.schema}"))))
            }
            if (table.primaryKey.isNotEmpty()) {
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    cls.iri, df.getOWLAnnotation(df.rdfsComment,
                        df.getOWLLiteral("PK: " + table.primaryKey.joinToString(", ")))))
            }

            // FK 컬럼은 DataProperty로 중복 생성하지 않는다 (Task 4에서 ObjectProperty로 승격)
            val fkColumns = table.foreignKeys.flatMap { it.fkColumns }.toHashSet()
            for (col in table.columns) {
                if (col.name in fkColumns) continue
                val dp = df.getOWLDataProperty(dataPropIri(baseIri, table, col.name))
                mgr.addAxiom(ont, df.getOWLDeclarationAxiom(dp))
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    dp.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(col.name))))
                mgr.addAxiom(ont, df.getOWLDataPropertyDomainAxiom(dp, cls))
                mgr.addAxiom(ont, df.getOWLDataPropertyRangeAxiom(
                    dp, df.getOWLDatatype(IRI.create(sqlTypeToXsd(col.sqlType)))))
            }

            for (fk in table.foreignKeys) {
                val op = df.getOWLObjectProperty(fkPropIri(baseIri, table, fk.fkColumns))
                val (targetIri, refLabel) = refTarget(baseIri, table, fk, byQualified, byName)
                val target = df.getOWLClass(targetIri)
                mgr.addAxiom(ont, df.getOWLDeclarationAxiom(op))
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    op.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(
                        "${table.qualifiedName} → $refLabel (${fk.fkColumns.joinToString(", ")})"))))
                mgr.addAxiom(ont, df.getOWLObjectPropertyDomainAxiom(op, cls))
                mgr.addAxiom(ont, df.getOWLObjectPropertyRangeAxiom(op, target))
                // FK 유래 관계: 최고 신뢰도 EXTRACTED로 provenance 부착
                fun anno(propIri: String, value: String) = mgr.addAxiom(
                    ont,
                    df.getOWLAnnotationAssertionAxiom(
                        op.iri,
                        df.getOWLAnnotation(df.getOWLAnnotationProperty(IRI.create(propIri)), df.getOWLLiteral(value))
                    )
                )
                anno(ProvenanceVocab.KIND, RelationKind.FK.name)
                anno(ProvenanceVocab.PROVENANCE, Provenance.EXTRACTED.name)
                anno(ProvenanceVocab.CONFIDENCE, "1.0")
            }
        }
        return ont
    }
}
