package com.ontostudio.readmodel

import com.ontostudio.align.AlignmentService
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import com.ontostudio.ontology.PropertyService
import com.ontostudio.savepoint.ConfirmationStore
import org.springframework.stereotype.Service
import java.sql.Connection
import java.sql.DriverManager

/**
 * OWL 온톨로지를 읽기 전용 SQLite 스키마(class/relation/evidence/alignment/domain/meta)로 투영한다(E16-1).
 * 이 태스크는 스키마 생성만 담당하며, 데이터 적재는 후속 태스크에서 추가된다.
 */
@Service
class ReadModelProjector(
    private val holder: OntologyHolder,
    private val mapper: OntologyMapper,
    private val classService: ClassService,
    private val propertyService: PropertyService,
    private val alignmentService: AlignmentService,
    private val confirmations: ConfirmationStore,
) {
    fun project(dbPath: String) = synchronized(holder.lock) {
        DriverManager.getConnection("jdbc:sqlite:$dbPath").use { c ->
            c.autoCommit = false
            createSchema(c)
            c.commit()
        }
    }

    private fun createSchema(c: Connection) {
        c.createStatement().use { st ->
            st.executeUpdate("DROP TABLE IF EXISTS class")
            st.executeUpdate("DROP TABLE IF EXISTS relation")
            st.executeUpdate("DROP TABLE IF EXISTS evidence")
            st.executeUpdate("DROP TABLE IF EXISTS alignment")
            st.executeUpdate("DROP TABLE IF EXISTS domain")
            st.executeUpdate("DROP TABLE IF EXISTS meta")
            st.executeUpdate("""CREATE TABLE class(iri TEXT PRIMARY KEY, label TEXT, orig_table TEXT,
                domain_id INTEGER, community INTEGER, degree INTEGER, confirmed INTEGER)""")
            st.executeUpdate("""CREATE TABLE relation(id INTEGER PRIMARY KEY, from_iri TEXT, to_iri TEXT,
                name TEXT, kind TEXT, provenance TEXT, confidence REAL)""")
            st.executeUpdate("""CREATE TABLE evidence(relation_id INTEGER, match_type TEXT, matched_on TEXT,
                alternatives_json TEXT, cardinality TEXT)""")
            st.executeUpdate("""CREATE TABLE alignment(source_iri TEXT, target_iri TEXT, match_type TEXT,
                confidence REAL, provenance TEXT)""")
            st.executeUpdate("CREATE TABLE domain(id INTEGER PRIMARY KEY, name TEXT, member_count INTEGER)")
            st.executeUpdate("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
            st.executeUpdate("CREATE INDEX idx_rel_from ON relation(from_iri)")
            st.executeUpdate("CREATE INDEX idx_rel_to ON relation(to_iri)")
            st.executeUpdate("CREATE INDEX idx_class_comm ON class(community)")
            st.executeUpdate("CREATE INDEX idx_class_label ON class(label)")
            st.executeUpdate("CREATE INDEX idx_class_table ON class(orig_table)")
        }
    }
}
