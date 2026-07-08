package com.ontostudio.readmodel

import com.ontostudio.align.AlignmentService
import com.ontostudio.core.OntologyHolder
import com.ontostudio.core.OntologyMapper
import com.ontostudio.ontology.ClassService
import com.ontostudio.ontology.PropertyService
import com.ontostudio.provenance.Provenance
import com.ontostudio.provenance.RelationKind
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
        val classes = classService.list()
        val rels = propertyService.listObject()
        val aligns = alignmentService.list()
        // degree = 관계에서 from/to로 등장한 횟수
        val degree = HashMap<String, Int>()
        rels.forEach { r ->
            val from = r.domains.firstOrNull()
            val to = r.ranges.firstOrNull()
            if (from != null && to != null) {
                degree[from] = (degree[from] ?: 0) + 1
                degree[to] = (degree[to] ?: 0) + 1
            }
        }
        DriverManager.getConnection("jdbc:sqlite:$dbPath").use { c ->
            c.autoCommit = false
            createSchema(c)
            c.prepareStatement("INSERT INTO class(iri,label,orig_table,domain_id,community,degree,confirmed) VALUES(?,?,?,?,?,?,?)").use { ps ->
                for (cl in classes) {
                    ps.setString(1, cl.iri); ps.setString(2, cl.label)
                    ps.setString(3, shortName(cl.iri))
                    ps.setObject(4, null); ps.setObject(5, null)
                    ps.setInt(6, degree[cl.iri] ?: 0)
                    ps.setInt(7, if (confirmations.isConfirmed(cl.iri)) 1 else 0)
                    ps.addBatch()
                }
                ps.executeBatch()
            }
            c.prepareStatement("INSERT INTO relation(from_iri,to_iri,name,kind,provenance,confidence) VALUES(?,?,?,?,?,?)").use { ps ->
                for (r in rels) {
                    val from = r.domains.firstOrNull() ?: continue
                    val to = r.ranges.firstOrNull() ?: continue
                    ps.setString(1, from); ps.setString(2, to)
                    ps.setString(3, r.label ?: shortName(r.iri))
                    ps.setString(4, (r.provenance?.kind ?: RelationKind.MANUAL).name)
                    ps.setString(5, (r.provenance?.provenance)?.name ?: Provenance.EXTRACTED.name)
                    if (r.provenance?.confidence != null) ps.setDouble(6, r.provenance!!.confidence!!) else ps.setNull(6, java.sql.Types.REAL)
                    ps.addBatch()
                }
                ps.executeBatch()
            }
            c.prepareStatement("INSERT INTO alignment(source_iri,target_iri,match_type,confidence,provenance) VALUES(?,?,?,?,?)").use { ps ->
                for (a in aligns) {
                    ps.setString(1, a.sourceIri); ps.setString(2, a.targetIri)
                    ps.setString(3, a.matchType.name)
                    if (a.confidence != null) ps.setDouble(4, a.confidence) else ps.setNull(4, java.sql.Types.REAL)
                    ps.setString(5, a.provenance)
                    ps.addBatch()
                }
                ps.executeBatch()
            }
            c.prepareStatement("INSERT INTO meta(key,value) VALUES(?,?)").use { ps ->
                fun put(k: String, v: String) { ps.setString(1, k); ps.setString(2, v); ps.addBatch() }
                put("classes", classes.size.toString())
                put("relations", rels.size.toString())
                put("alignments", aligns.size.toString())
                put("ontologyIri", holder.ontology.ontologyID.ontologyIRI.orElse(null)?.toString() ?: "")
                ps.executeBatch()
            }
            c.commit()
        }
    }

    private fun shortName(iri: String): String {
        val hash = iri.substringAfterLast('#', iri)
        return hash.substringAfterLast('/', hash)
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
