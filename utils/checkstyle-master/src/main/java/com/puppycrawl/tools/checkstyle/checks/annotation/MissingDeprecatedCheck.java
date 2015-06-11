////////////////////////////////////////////////////////////////////////////////
// checkstyle: Checks Java source code for adherence to a set of rules.
// Copyright (C) 2001-2015 the original author or authors.
//
// This library is free software; you can redistribute it and/or
// modify it under the terms of the GNU Lesser General Public
// License as published by the Free Software Foundation; either
// version 2.1 of the License, or (at your option) any later version.
//
// This library is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public
// License along with this library; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
////////////////////////////////////////////////////////////////////////////////

package com.puppycrawl.tools.checkstyle.checks.annotation;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.puppycrawl.tools.checkstyle.AnnotationUtility;
import com.puppycrawl.tools.checkstyle.api.Check;
import com.puppycrawl.tools.checkstyle.api.DetailAST;
import com.puppycrawl.tools.checkstyle.api.JavadocTagInfo;
import com.puppycrawl.tools.checkstyle.api.TextBlock;
import com.puppycrawl.tools.checkstyle.api.TokenTypes;
import com.puppycrawl.tools.checkstyle.Utils;

/**
 * <p>
 * This class is used to verify that both the
 * {@link java.lang.Deprecated Deprecated} annotation
 * and the deprecated javadoc tag are present when
 * either one is present.
 * </p>
 *
 * <p>
 * Both ways of flagging deprecation serve their own purpose.  The
 * {@link java.lang.Deprecated Deprecated} annotation is used for
 * compilers and development tools.  The deprecated javadoc tag is
 * used to document why something is deprecated and what, if any,
 * alternatives exist.
 * </p>
 *
 * <p>
 * In order to properly mark something as deprecated both forms of
 * deprecation should be present.
 * </p>
 *
 * <p>
 * Package deprecation is a exception to the rule of always using the
 * javadoc tag and annotation to deprecate.  Only the package-info.java
 * file can contain a Deprecated annotation and it CANNOT contain
 * a deprecated javadoc tag.  This is the case with
 * Sun's javadoc tool released with JDK 1.6.0_11.  As a result, this check
 * does not deal with Deprecated packages in any way.  <b>No official
 * documentation was found confirming this behavior is correct
 * (of the javadoc tool).</b>
 * </p>
 *
 * <p>
 * To configure this check do the following:
 * </p>
 *
 * <pre>
 * &lt;module name="JavadocDeprecated"/&gt;
 * </pre>
 *
 * @author Travis Schneeberger
 */
public final class MissingDeprecatedCheck extends Check {
    /**
     * A key is pointing to the warning message text in "messages.properties"
     * file.
     */
    public static final String MSG_KEY_ANNOTATION_MISSING_DEPRECATED =
            "annotation.missing.deprecated";

    /**
     * A key is pointing to the warning message text in "messages.properties"
     * file.
     */
    public static final String MSG_KEY_JAVADOC_DUPLICATE_TAG =
            "javadoc.duplicateTag";

    /**
     * A key is pointing to the warning message text in "messages.properties"
     * file.
     */
    public static final String MSG_KEY_JAVADOC_MISSING = "javadoc.missing";

    /** {@link Deprecated Deprecated} annotation name */
    private static final String DEPRECATED = "Deprecated";

    /** fully-qualified {@link Deprecated Deprecated} annotation name */
    private static final String FQ_DEPRECATED = "java.lang." + DEPRECATED;

    /** compiled regexp to match Javadoc tag with no argument * */
    private static final Pattern MATCH_DEPRECATED =
        Utils.createPattern("@(deprecated)\\s+\\S");

    /** compiled regexp to match first part of multilineJavadoc tags * */
    private static final Pattern MATCH_DEPRECATED_MULTILINE_START =
        Utils.createPattern("@(deprecated)\\s*$");

    /** compiled regexp to look for a continuation of the comment * */
    private static final Pattern MATCH_DEPRECATED_MULTILINE_CONT =
        Utils.createPattern("(\\*/|@|[^\\s\\*])");

    /** Multiline finished at end of comment * */
    private static final String END_JAVADOC = "*/";
    /** Multiline finished at next Javadoc * */
    private static final String NEXT_TAG = "@";

    /** {@inheritDoc} */
    @Override
    public int[] getDefaultTokens() {
        return this.getAcceptableTokens();
    }

    /** {@inheritDoc} */
    @Override
    public int[] getAcceptableTokens() {
        return new int[] {
            TokenTypes.INTERFACE_DEF,
            TokenTypes.CLASS_DEF,
            TokenTypes.ANNOTATION_DEF,
            TokenTypes.ENUM_DEF,
            TokenTypes.METHOD_DEF,
            TokenTypes.CTOR_DEF,
            TokenTypes.VARIABLE_DEF,
            TokenTypes.ENUM_CONSTANT_DEF,
            TokenTypes.ANNOTATION_FIELD_DEF,
        };
    }

    /** {@inheritDoc} */
    @Override
    public void visitToken(final DetailAST ast) {
        final TextBlock javadoc =
            this.getFileContents().getJavadocBefore(ast.getLineNo());

        final boolean containsAnnotation =
            AnnotationUtility.containsAnnotation(ast, DEPRECATED)
            || AnnotationUtility.containsAnnotation(ast, FQ_DEPRECATED);

        final boolean containsJavadocTag = this.containsJavadocTag(javadoc);

        if (containsAnnotation ^ containsJavadocTag) {
            this.log(ast.getLineNo(), MSG_KEY_ANNOTATION_MISSING_DEPRECATED);
        }
    }

    /**
     * Checks to see if the text block contains a deprecated tag.
     *
     * @param javadoc the javadoc of the AST
     * @return true if contains the tag
     */
    private boolean containsJavadocTag(final TextBlock javadoc) {
        if (javadoc == null) {
            return false;
        }

        final String[] lines = javadoc.getText();

        boolean found = false;

        int currentLine = javadoc.getStartLineNo() - 1;

        for (int i = 0; i < lines.length; i++) {
            currentLine++;
            final String line = lines[i];

            final Matcher javadocNoargMatcher =
                MissingDeprecatedCheck.MATCH_DEPRECATED.matcher(line);
            final Matcher noargMultilineStart =
                MissingDeprecatedCheck
                    .MATCH_DEPRECATED_MULTILINE_START.matcher(line);

            if (javadocNoargMatcher.find()) {
                if (found) {
                    this.log(currentLine, MSG_KEY_JAVADOC_DUPLICATE_TAG,
                        JavadocTagInfo.DEPRECATED.getText());
                }
                found = true;
            }
            else if (noargMultilineStart.find()) {
                // Look for the rest of the comment if all we saw was
                // the tag and the name. Stop when we see '*/' (end of
                // Javadoc), '@' (start of next tag), or anything that's
                // not whitespace or '*' characters.

                for (int reindex = i + 1;
                    reindex < lines.length; reindex++) {
                    final Matcher multilineCont =
                        MissingDeprecatedCheck.MATCH_DEPRECATED_MULTILINE_CONT
                        .matcher(lines[reindex]);

                    if (multilineCont.find()) {
                        reindex = lines.length;
                        final String lFin = multilineCont.group(1);
                        if (!lFin.equals(MissingDeprecatedCheck.NEXT_TAG)
                            && !lFin.equals(MissingDeprecatedCheck.END_JAVADOC)) {
                            if (found) {
                                this.log(currentLine, MSG_KEY_JAVADOC_DUPLICATE_TAG,
                                    JavadocTagInfo.DEPRECATED.getText());
                            }
                            found = true;
                        }
                        else {
                            this.log(currentLine, MSG_KEY_JAVADOC_MISSING);
                            if (found) {
                                this.log(currentLine, MSG_KEY_JAVADOC_DUPLICATE_TAG,
                                    JavadocTagInfo.DEPRECATED.getText());
                            }
                            found = true;
                        }
                    }
                }
            }
        }
        return found;
    }
}