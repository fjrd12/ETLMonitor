<xsl:template match="/">
    <xsl:variable name="idoc" select="(//*[local-name()='IDOC'])[1]"/>
    <xsl:variable name="control" select="$idoc/*[local-name()='EDI_DC40'][1]"/>
    <xsl:variable name="mestyp" select="normalize-space($control/*[local-name()='MESTYP'])"/>
    <xsl:variable name="idoctyp" select="normalize-space($control/*[local-name()='IDOCTYP'])"/>
    <xsl:choose>
      <xsl:when test="$mestyp='INVOIC' and $idoctyp='INVOIC02'">
        <xsl:variable name="currency"
          select="normalize-space($idoc/*[local-name()='E1EDK01'][1]/*[local-name()='CURCY'])"/>
        <xsl:variable name="sum011"
          select="$idoc/*[local-name()='E1EDS01'][normalize-space(*[local-name()='SUMID'])='011']/*[local-name()='SUMME'][normalize-space(.)!='']"/>
        <xsl:variable name="sum010"
          select="$idoc/*[local-name()='E1EDS01'][normalize-space(*[local-name()='SUMID'])='010']/*[local-name()='SUMME'][normalize-space(.)!='']"/>
        <xsl:variable name="item003"
          select="$idoc//*[local-name()='E1EDP26'][normalize-space(*[local-name()='QUALF'])='003']/*[local-name()='BETRG'][normalize-space(.)!='']"/>
        <xsl:variable name="item005"
          select="$idoc//*[local-name()='E1EDP26'][normalize-space(*[local-name()='QUALF'])='005']/*[local-name()='BETRG'][normalize-space(.)!='']"/>
        <IDOC_VALUATION>
          <DOCNUM><xsl:value-of select="$control/*[local-name()='DOCNUM']"/></DOCNUM>
          <MESTYP>INVOIC</MESTYP>
          <IDOCTYP>INVOIC02</IDOCTYP>
          <VALUATIONS>
            <xsl:choose>
              <xsl:when test="count($sum011)&gt;0">
                <VALUATION primary="true"><TYPE>AMOUNT</TYPE><VALUE><xsl:value-of select="format-number(number($sum011[1]),'0.##########')"/></VALUE><UNIT><xsl:value-of select="$currency"/></UNIT><SOURCE>E1EDS01[SUMID='011']/SUMME</SOURCE><STATUS>VALUATED</STATUS></VALUATION>
              </xsl:when>
              <xsl:when test="count($sum010)&gt;0">
                <VALUATION primary="true"><TYPE>AMOUNT</TYPE><VALUE><xsl:value-of select="format-number(number($sum010[1]),'0.##########')"/></VALUE><UNIT><xsl:value-of select="$currency"/></UNIT><SOURCE>E1EDS01[SUMID='010']/SUMME</SOURCE><STATUS>VALUATED</STATUS></VALUATION>
              </xsl:when>
              <xsl:when test="count($item003)&gt;0">
                <VALUATION primary="true"><TYPE>AMOUNT</TYPE><VALUE><xsl:value-of select="format-number(sum($item003),'0.##########')"/></VALUE><UNIT><xsl:value-of select="$currency"/></UNIT><SOURCE>E1EDP26[QUALF='003']/BETRG</SOURCE><STATUS>VALUATED</STATUS></VALUATION>
              </xsl:when>
              <xsl:when test="count($item005)&gt;0">
                <VALUATION primary="true"><TYPE>AMOUNT</TYPE><VALUE><xsl:value-of select="format-number(sum($item005),'0.##########')"/></VALUE><UNIT><xsl:value-of select="$currency"/></UNIT><SOURCE>E1EDP26[QUALF='005']/BETRG</SOURCE><STATUS>VALUATED</STATUS></VALUATION>
              </xsl:when>
              <xsl:otherwise>
                <VALUATION primary="true"><TYPE>AMOUNT</TYPE><VALUE>0</VALUE><UNIT><xsl:value-of select="$currency"/></UNIT><SOURCE>INVOIC02 valuation rule</SOURCE><STATUS>UNAVAILABLE</STATUS></VALUATION>
              </xsl:otherwise>
            </xsl:choose>
          </VALUATIONS>
        </IDOC_VALUATION>
      </xsl:when>
      <xsl:otherwise>
        <IDOC_VALUATION><STATUS>UNSUPPORTED_MESTYP_OR_IDOCTYP</STATUS><EXPECTED>INVOIC / INVOIC02</EXPECTED></IDOC_VALUATION>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>