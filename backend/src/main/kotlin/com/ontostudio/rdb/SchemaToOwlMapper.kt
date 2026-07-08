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

    internal fun classIri(base: String, table: String): IRI = IRI.create(base + slug(table))
    internal fun dataPropIri(base: String, table: String, column: String): IRI =
        IRI.create(base + slug(table) + "." + slug(column))

    internal fun fkPropIri(base: String, table: String, fkColumns: List<String>): IRI =
        IRI.create(base + slug(table) + "_" + fkColumns.joinToString("_") { slug(it) } + "_ref")

    fun build(schema: SchemaModel, baseIri: String): OWLOntology {
        val mgr = OWLManager.createOWLOntologyManager()
        val df = mgr.owlDataFactory
        val ont = mgr.createOntology()

        for (table in schema.tables) {
            val cls = df.getOWLClass(classIri(baseIri, table.name))
            mgr.addAxiom(ont, df.getOWLDeclarationAxiom(cls))
            mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                cls.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(table.name))))
            if (table.primaryKey.isNotEmpty()) {
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    cls.iri, df.getOWLAnnotation(df.rdfsComment,
                        df.getOWLLiteral("PK: " + table.primaryKey.joinToString(", ")))))
            }

            // FK 컬럼은 DataProperty로 중복 생성하지 않는다 (Task 4에서 ObjectProperty로 승격)
            val fkColumns = table.foreignKeys.flatMap { it.fkColumns }.toHashSet()
            for (col in table.columns) {
                if (col.name in fkColumns) continue
                val dp = df.getOWLDataProperty(dataPropIri(baseIri, table.name, col.name))
                mgr.addAxiom(ont, df.getOWLDeclarationAxiom(dp))
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    dp.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(col.name))))
                mgr.addAxiom(ont, df.getOWLDataPropertyDomainAxiom(dp, cls))
                mgr.addAxiom(ont, df.getOWLDataPropertyRangeAxiom(
                    dp, df.getOWLDatatype(IRI.create(sqlTypeToXsd(col.sqlType)))))
            }

            for (fk in table.foreignKeys) {
                val op = df.getOWLObjectProperty(fkPropIri(baseIri, table.name, fk.fkColumns))
                val target = df.getOWLClass(classIri(baseIri, fk.refTable))
                mgr.addAxiom(ont, df.getOWLDeclarationAxiom(op))
                mgr.addAxiom(ont, df.getOWLAnnotationAssertionAxiom(
                    op.iri, df.getOWLAnnotation(df.rdfsLabel, df.getOWLLiteral(
                        "${table.name} → ${fk.refTable} (${fk.fkColumns.joinToString(", ")})"))))
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
