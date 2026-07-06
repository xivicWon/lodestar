/**
 * IRI에서 원본 식별자(테이블명 등)를 뽑는다.
 * enrich로 label이 업무명으로 바뀌어도 IRI 프래그먼트엔 원본 테이블명이 남는다.
 * 예: "http://x/rdb/ops#tb_ast_chk_lst" → "tb_ast_chk_lst"
 */
export function shortName(iri: string): string {
  const hash = iri.split('#').pop() ?? iri
  return hash.split('/').pop() ?? hash
}
