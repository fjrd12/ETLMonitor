<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="yes"/>

  <xsl:key name="matnr-unit" match="E1EDL44" use="concat(normalize-space(MATNR),'|',normalize-space(VEMEH))"/>

  <xsl:template match="/">
    <xsl:variable name="idoc" select="(//*[local-name()='IDOC'])[1]"/>
    <xsl:variable name="control" select="$idoc/*[local-name()='EDI_DC40'][1]"/>
    <xsl:variable name="mestyp" select="normalize-space($control/*[local-name()='MESTYP'])"/>
    <xsl:variable name="idoctyp" select="normalize-space($control/*[local-name()='IDOCTYP'])"/>
    <xsl:choose>
      <xsl:when test="$mestyp='ZSHPMNT858' and $idoctyp='SHPMNT05'">
        <xsl:variable name="items" select="$idoc/*[local-name()='E1EDL44']"/>
        <IDOC_VALUATION>
          <DOCNUM><xsl:value-of select="$control/*[local-name()='DOCNUM']"/></DOCNUM>
          <MESTYP>ZSHPMNT858</MESTYP>
          <IDOCTYP>SHPMNT05</IDOCTYP>
          <VALUATIONS>
            <xsl:for-each select="$items[
              normalize-space(*[local-name()='VEMEH'])!='' and
              generate-id()=generate-id(key('matnr-unit',concat(normalize-space(*[local-name()='MATNR']),'|',normalize-space(*[local-name()='VEMEH'])))[1])]">
              <xsl:variable name="matnr" select="normalize-space(*[local-name()='MATNR'])"/>
              <xsl:variable name="u" select="normalize-space(*[local-name()='VEMEH'])"/>
              <xsl:variable name="k" select="concat($matnr,'|',$u)"/>
              <VALUATION>
                <xsl:attribute name="primary"><xsl:choose><xsl:when test="position()=1">true</xsl:when><xsl:otherwise>false</xsl:otherwise></xsl:choose></xsl:attribute>
                <TYPE>QUANTITY</TYPE>
                <VALUE><xsl:value-of select="format-number(sum(key('matnr-unit',$k)/*[local-name()='VEMNG']),'0.##########')"/></VALUE>
                <UNIT><xsl:value-of select="$u"/></UNIT>
                <SOURCE><xsl:value-of select="concat('E1EDL44[MATNR=',$matnr,']/VEMNG + VEMEH')"/></SOURCE>
                <STATUS>VALUATED</STATUS>
              </VALUATION>
            </xsl:for-each>
          </VALUATIONS>
        </IDOC_VALUATION>
      </xsl:when>
      <xsl:otherwise>
        <IDOC_VALUATION><STATUS>UNSUPPORTED_MESTYP_OR_IDOCTYP</STATUS><EXPECTED>ZSHPMNT858 / SHPMNT05</EXPECTED></IDOC_VALUATION>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:stylesheet>
