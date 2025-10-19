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
            func main(x: u32, y: u32) {
                if (x < y) {
                    return;
                } 
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var functionDefinition = Parser.ParseFunctionDefinition(tokenReader);
        var returnsOnAllPathAnalyzer = new ReturnsOnAllPathAnalyzer();
        functionDefinition.Body.Accept(returnsOnAllPathAnalyzer);
        Assert.That(returnsOnAllPathAnalyzer.Result, Is.False);
    }
    
    [Test]
    public void TestReturnsOnAllPaths_SimpleFunctionWithReturnType()
    {
        const string input =
            """
            func main(x: u32, y: u32) -> u32{
                if (x < y) {
                    return;
                } 
                return;
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var functionDefinition = Parser.ParseFunctionDefinition(tokenReader);
        var expressionTypeAnalyzer = new ExpressionTypeAnalyzer();
        var returnsOnAllPathAnalyzer = new ReturnsOnAllPathAnalyzer
        {
            ExpectedReturnType = new NamedTypeNode
            {
                Identifier = "u32"
            }
        };
        functionDefinition.Body.Accept(returnsOnAllPathAnalyzer);
        Assert.That(returnsOnAllPathAnalyzer.Result, Is.False);
    }
}