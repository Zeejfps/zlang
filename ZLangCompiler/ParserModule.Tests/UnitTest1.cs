using LexerModule;

namespace ParserModule.Tests;

public class Tests
{
    [SetUp]
    public void Setup()
    {
    }

    //[Test]
    public void Test1()
    {
        const string input = "var test: u32 = 10;";
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        var printer = new AstPrinter();
        ast.Root.Accept(printer);
        var result = printer.ToString();
        Assert.Pass();
    }
    
    [Test]
    public void TestBinaryExpression()
    {
        const string input = "10 + 5";
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseBinaryExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        Assert.Pass();
    }
    
    [Test]
    public void TestExpression()
    {
        const string input = "10 + 5 * 10";
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseBinaryExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        Assert.Pass();
    }
    
    [Test]
    public void TestPrimaryExpressionNumber()
    {
        const string input = "10";
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParsePrimaryExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        Assert.Pass();
    }
}