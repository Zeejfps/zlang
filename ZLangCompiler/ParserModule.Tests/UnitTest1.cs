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
        var astNode = Parser.ParseExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        Assert.Pass();
    }
    
    [Test]
    public void TestExpression()
    {
        const string input = "10 + 5 * 10 - 29 / -30";
        Console.WriteLine(input);
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        
        Assert.Pass();
    }
    
    [Test]
    public void TestExpressionWithParanthesis()
    {
        const string input = "10 + 5 * (10 - 29) / -30";
        Console.WriteLine(input);
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        
        Assert.Pass();
    }
    
    [Test]
    public void TestExpressionWithIdentifiers()
    {
        const string input = "10 + x * (x - 29) / -y";
        Console.WriteLine(input);
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
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
    
    [Test]
    public void TestVarAssignmentStatement()
    {
        const string input = "var x: u32 = 1337;";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseVarAssignmentStatement(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        Assert.Pass();
    }
}