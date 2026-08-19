<xsl:template match="/">
    <xsl:variable name="idoc" select="(//*[local-name()='IDOC'])[1]"/>
    <xsl:variable name="control" select="$idoc/*[local-name()='EDI_DC40'][1]"/>
    <xsl:variable name="mestyp" select="normalize-space($control/*[local-name()='MESTYP'])"/>
    <xsl:variable name="idoctyp" select="normalize-space($control/*[local-name()='IDOCTYP'])"/>
    <xsl:choose>
      <xsl:when test="$mestyp='PROJECT' and $idoctyp='PROJECT02'">
        <xsl:variable name="wbs"
          select="$idoc/*[local-name()='E1BP2054_MASTERDATA_ALE']
                         [normalize-space(*[local-name()='WBS_ELEMENT'])!='']"/>
        <IDOC_VALUATION>
          <DOCNUM><xsl:value-of select="$control/*[local-name()='DOCNUM']"/></DOCNUM>
          <MESTYP>PROJECT</MESTYP>
          <IDOCTYP>PROJECT02</IDOCTYP>
          <VALUATIONS>
            <VALUATION primary="true">
              <TYPE>OBJECT_COUNT</TYPE>
              <VALUE><xsl:value-of select="count($wbs)"/></VALUE>
              <UNIT>WBS</UNIT>
              <SOURCE>E1BP2054_MASTERDATA_ALE/WBS_ELEMENT</SOURCE>
              <STATUS>VALUATED</STATUS>
            </VALUATION>
          </VALUATIONS>
        </IDOC_VALUATION>
      </xsl:when>
      <xsl:otherwise>
        <IDOC_VALUATION>
          <STATUS>UNSUPPORTED_MESTYP_OR_IDOCTYP</STATUS>
          <EXPECTED>PROJECT / PROJECT02</EXPECTED>
        </IDOC_VALUATION>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>