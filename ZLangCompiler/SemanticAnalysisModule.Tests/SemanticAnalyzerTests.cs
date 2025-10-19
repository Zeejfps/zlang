using LexerModule;
using ParserModule;
using ParserModule.Nodes;

namespace SemanticAnalysisModule.Tests;

public class SemanticAnalyzerTests
{
    [SetUp]
    public void Setup()
    {
    }
    
    [Test]
    public void TestReturnsOnAllPaths_SimpleBlockStatementWithIf()
    {
        const string input =
            """
            {
                if (x < y) {
                    return;
                } 
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var blockStatement = Parser.ParseBlockStatement(tokenReader);
        var returnsOnAllPathAnalyzer = new ReturnsOnAllPathAnalyzer();
        blockStatement.Accept(returnsOnAllPathAnalyzer);
        Assert.That(returnsOnAllPathAnalyzer.Result, Is.False);
    }
    
    [Test]
    public void TestReturnsOnAllPaths_SimpleFunction()
    {
        const string input =
            """
            {
                if (x < y) {
                    return;
                } 
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var blockStatement = Parser.ParseBlockStatement(tokenReader);
        var returnsOnAllPathAnalyzer = new ReturnsOnAllPathAnalyzer();
        blockStatement.Accept(returnsOnAllPathAnalyzer);
        Assert.That(returnsOnAllPathAnalyzer.Result, Is.False);
    }
}