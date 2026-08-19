<xsl:key name="qty-unit"
           match="E1EDP01[not(UEPOS) or normalize-space(UEPOS)='' or number(UEPOS)=0]"
           use="normalize-space(MENEE)"/>
  <xsl:template match="/">
    <xsl:variable name="idoc" select="(//*[local-name()='IDOC'])[1]"/>
    <xsl:variable name="control" select="$idoc/*[local-name()='EDI_DC40'][1]"/>
    <xsl:variable name="mestyp" select="normalize-space($control/*[local-name()='MESTYP'])"/>
    <xsl:variable name="idoctyp" select="normalize-space($control/*[local-name()='IDOCTYP'])"/>
    <xsl:variable name="cimtyp" select="normalize-space($control/*[local-name()='CIMTYP'])"/>
    <xsl:choose>
      <xsl:when test="$mestyp='ORDERS' and $idoctyp='ORDERS05'">
        <xsl:variable name="currency"
          select="normalize-space($idoc/*[local-name()='E1EDK01'][1]/*[local-name()='CURCY'])"/>
        <xsl:variable name="topItems"
          select="$idoc/*[local-name()='E1EDP01']
            [not(*[local-name()='UEPOS']) or normalize-space(*[local-name()='UEPOS'])='' or number(*[local-name()='UEPOS'])=0]"/>
        <xsl:variable name="netwrNodes"
          select="$topItems/*[local-name()='NETWR'][normalize-space(.)!='']"/>
        <xsl:variable name="zpnqNodes"
          select="$topItems/*[local-name()='E1EDP05']
            [normalize-space(*[local-name()='KSCHL'])='ZPNQ']
            /*[local-name()='BETRG'][normalize-space(.)!='']"/>
        <IDOC_VALUATION>
          <DOCNUM><xsl:value-of select="$control/*[local-name()='DOCNUM']"/></DOCNUM>
          <MESTYP>ORDERS</MESTYP>
          <IDOCTYP>ORDERS05</IDOCTYP>
          <xsl:if test="$cimtyp!=''"><CIMTYP><xsl:value-of select="$cimtyp"/></CIMTYP></xsl:if>
          <VALUATIONS>
            <xsl:choose>
              <xsl:when test="$cimtyp='ZFULFILLORDERS' and count($zpnqNodes)&gt;0">
                <VALUATION primary="true">
                  <TYPE>AMOUNT</TYPE>
                  <VALUE><xsl:value-of select="format-number(sum($zpnqNodes),'0.##########')"/></VALUE>
                  <UNIT><xsl:value-of select="$currency"/></UNIT>
                  <SOURCE>E1EDP01[top-level]/E1EDP05[KSCHL='ZPNQ']/BETRG</SOURCE>
                  <STATUS>VALUATED</STATUS>
                </VALUATION>
              </xsl:when>
              <xsl:when test="count($netwrNodes)&gt;0">
                <VALUATION primary="true">
                  <TYPE>AMOUNT</TYPE>
                  <VALUE><xsl:value-of select="format-number(sum($netwrNodes),'0.##########')"/></VALUE>
                  <UNIT><xsl:value-of select="$currency"/></UNIT>
                  <SOURCE>E1EDP01[top-level]/NETWR</SOURCE>
                  <STATUS>VALUATED</STATUS>
                </VALUATION>
              </xsl:when>
              <xsl:otherwise>
                <VALUATION primary="true">
                  <TYPE>QUANTITY</TYPE>
                  <VALUE><xsl:value-of select="format-number(sum($topItems/*[local-name()='MENGE']),'0.##########')"/></VALUE>
                  <UNIT><xsl:value-of select="normalize-space($topItems[1]/*[local-name()='MENEE'])"/></UNIT>
                  <SOURCE>E1EDP01[top-level]/MENGE</SOURCE>
                  <STATUS>VALUATED_WITH_OPERATIONAL_FALLBACK</STATUS>
                </VALUATION>
              </xsl:otherwise>
            </xsl:choose>
          </VALUATIONS>
        </IDOC_VALUATION>
      </xsl:when>
      <xsl:otherwise>
        <IDOC_VALUATION><STATUS>UNSUPPORTED_MESTYP_OR_IDOCTYP</STATUS><EXPECTED>ORDERS / ORDERS05</EXPECTED></IDOC_VALUATION>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>