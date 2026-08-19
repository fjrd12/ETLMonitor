<xsl:key name="qty-unit" match="E1EDL24" use="normalize-space(VRKME)"/>
  <xsl:key name="weight-unit" match="E1EDL24" use="normalize-space(GEWEI)"/>
  <xsl:key name="volume-unit" match="E1EDL24" use="normalize-space(VOLEH)"/>
  <xsl:template match="/">
    <xsl:variable name="idoc" select="(//*[local-name()='IDOC'])[1]"/>
    <xsl:variable name="control" select="$idoc/*[local-name()='EDI_DC40'][1]"/>
    <xsl:variable name="mestyp" select="normalize-space($control/*[local-name()='MESTYP'])"/>
    <xsl:variable name="idoctyp" select="normalize-space($control/*[local-name()='IDOCTYP'])"/>
    <xsl:choose>
      <xsl:when test="$mestyp='SHPMNT' and $idoctyp='SHPMNT05'">
        <xsl:variable name="items" select="$idoc/*[local-name()='E1EDL24']"/>
        <IDOC_VALUATION>
          <DOCNUM><xsl:value-of select="$control/*[local-name()='DOCNUM']"/></DOCNUM>
          <MESTYP>SHPMNT</MESTYP>
          <IDOCTYP>SHPMNT05</IDOCTYP>
          <VALUATIONS>
            <xsl:for-each select="$items[
              normalize-space(*[local-name()='VRKME'])!='' and
              generate-id()=generate-id(key('qty-unit',normalize-space(*[local-name()='VRKME']))[1])]">
              <xsl:variable name="u" select="normalize-space(*[local-name()='VRKME'])"/>
              <VALUATION>
                <xsl:attribute name="primary"><xsl:choose><xsl:when test="position()=1">true</xsl:when><xsl:otherwise>false</xsl:otherwise></xsl:choose></xsl:attribute>
                <TYPE>QUANTITY</TYPE>
                <VALUE><xsl:value-of select="format-number(sum(key('qty-unit',$u)/*[local-name()='LFIMG']),'0.##########')"/></VALUE>
                <UNIT><xsl:value-of select="$u"/></UNIT>
                <SOURCE>E1EDL24/LFIMG + VRKME</SOURCE>
                <STATUS>VALUATED</STATUS>
              </VALUATION>
            </xsl:for-each>
            <xsl:for-each select="$items[
              normalize-space(*[local-name()='GEWEI'])!='' and
              generate-id()=generate-id(key('weight-unit',normalize-space(*[local-name()='GEWEI']))[1])]">
              <xsl:variable name="u" select="normalize-space(*[local-name()='GEWEI'])"/>
              <VALUATION primary="false">
                <TYPE>NET_WEIGHT</TYPE>
                <VALUE><xsl:value-of select="format-number(sum(key('weight-unit',$u)/*[local-name()='NTGEW']),'0.##########')"/></VALUE>
                <UNIT><xsl:value-of select="$u"/></UNIT>
                <SOURCE>E1EDL24/NTGEW + GEWEI</SOURCE>
                <STATUS>VALUATED</STATUS>
              </VALUATION>
            </xsl:for-each>
            <xsl:for-each select="$items[
              normalize-space(*[local-name()='VOLEH'])!='' and
              generate-id()=generate-id(key('volume-unit',normalize-space(*[local-name()='VOLEH']))[1])]">
              <xsl:variable name="u" select="normalize-space(*[local-name()='VOLEH'])"/>
              <VALUATION primary="false">
                <TYPE>VOLUME</TYPE>
                <VALUE><xsl:value-of select="format-number(sum(key('volume-unit',$u)/*[local-name()='VOLUM']),'0.##########')"/></VALUE>
                <UNIT><xsl:value-of select="$u"/></UNIT>
                <SOURCE>E1EDL24/VOLUM + VOLEH</SOURCE>
                <STATUS>VALUATED</STATUS>
              </VALUATION>
            </xsl:for-each>
          </VALUATIONS>
        </IDOC_VALUATION>
      </xsl:when>
      <xsl:otherwise>
        <IDOC_VALUATION><STATUS>UNSUPPORTED_MESTYP_OR_IDOCTYP</STATUS><EXPECTED>SHPMNT / SHPMNT05</EXPECTED></IDOC_VALUATION>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>